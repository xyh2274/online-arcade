/* 单元测试：键位「站点默认（按平台）+ 玩家只存改过的键 + 自动去重」
 *
 * 思路与既有测试一致：从**已打补丁的产物** Player-BwKb4RpM.js 里原样切出代码来跑，
 * 而不是在测试里重写一份逻辑 —— 那样测的是测试自己，不是线上跑的东西。
 */
const fs = require('fs')
const path = require('path')

const SRC = fs.readFileSync(path.join(__dirname, 'Player-BwKb4RpM.js'), 'utf8')

let pass = 0
let fail = 0
function ok(cond, name, extra) {
  if (cond) { pass++; console.log('  PASS  ' + name) }
  else { fail++; console.log('  FAIL  ' + name + (extra !== undefined ? '  -> ' + JSON.stringify(extra) : '')) }
}
function eq(a, b, name) { ok(JSON.stringify(a) === JSON.stringify(b), name, { got: a, want: b }) }

// 从源码里切一段（含起点、含终点）
function slice(from, to, start = 0) {
  const i = SRC.indexOf(from, start)
  if (i < 0) throw new Error('找不到起点: ' + from)
  const j = SRC.indexOf(to, i)
  if (j < 0) throw new Error('找不到终点: ' + to)
  return SRC.slice(i, j + to.length)
}

console.log('=== A) 产物里确实装上了各改动点 ===')
ok(SRC.includes('function e(o,l){var u;var _kb={...W.value.keyboard,[o]:l};'), 'setKeyboard 已改为先建 _kb')
ok(SRC.includes('/*[patch] kb-dedupe*/'), 'setKeyboard 带 kb-dedupe 标记')
ok(/function t\(o,l\)\{var u;var _gm=\{[\s\S]{0,80}kb-dedupe/.test(SRC), 'setGamepad 也带去重')
ok(SRC.includes('__arcadeEffKb') && SRC.includes('__arcadeEffGm'), 'Et / reset 走有效默认')
ok(SRC.includes('var _pk=(globalThis.__arcadeKeyPack?globalThis.__arcadeKeyPack(e):e);'), 'Ke 持久化前先 pack 成 diff')
ok(SRC.includes("api.load(n,(globalThis.__arcadeKeyPlatform)||'__global__')"), 'hd 按平台拉服务端')
ok(SRC.includes('globalThis.__arcadeSetKeyPlatform((n&&n.platform)||null)'), 'InputSettings 记录当前平台')
ok(SRC.includes('__arcadeKeyAdminUI'), '管理员 UI 钩子已注入')
ok(/var HARD_KB=\{up:"up"/.test(SRC), '硬编码 pt 已注入模块（键位同源）')
ok(/var HARD_GM=\{a:1,b:0/.test(SRC), '硬编码 ht 已注入模块')
ok(/if\(globalThis\.__arcadeKeyPlatformMod\)return;/.test(SRC), '模块有幂等守卫')
ok(SRC.trimEnd().endsWith('})();'), '末尾 IIFE 就地闭合')
// 回归守卫：不能破坏既有测试的切片锚点
ok(SRC.includes('};function __arcadePorts'), '回归守卫：保留 };function __arcadePorts 锚点')
// 重置/暂停浮动按钮
ok(SRC.includes('globalThis.__arcadeEmuInst=P'), 'nostalgist 实例暴露到 globalThis（Fn 内部 s.value=P 处）')
ok(SRC.includes('__arcadePadNames'), '手柄按钮号→标准名映射已注入')
ok(!SRC.includes('`按钮 ${y}`'), '回归守卫：旧的「按钮 ${y}」模板已移除')
ok(SRC.includes('__arcadeEmuBtnMod'), '重置/暂停浮动按钮模块已注入')
ok(SRC.includes('[patch] emu-buttons'), 'emu-buttons 补丁标记在')
ok(SRC.includes('/*[patch] uid-store'), '回归守卫：ai() 带 uid-store（uid 必须能解析真实用户，否则同步键位永远不生效）')

console.log('\n=== B) 加载模块并喂入站点默认 ===')
// ⚠ 不能用 indexOf('})();')：模块**内部**那个 api 覆盖 IIFE 也以 '})();' 结尾，会提前截断。
// ⚠ 也不能用 lastIndexOf('})();')：2026-09-15 之后文件末尾又追加了
//    [patch] keys-live / [patch] emu-buttons 两块，它们直接用 `document`，
//    在 Node 里 eval 会 "ReferenceError: document is not defined"（该测试曾因此长期假失败）。
//    真正需要的是 key-platform 这一段 → 切到下一个顶层 [patch] 块之前。
const modStart = SRC.indexOf('/*[patch] key-platform —— 站点默认键位')
const NEXT_TOP_BLOCK = '/*[patch] keys-live'
const _nextAt = SRC.indexOf(NEXT_TOP_BLOCK, modStart)
const modEnd = _nextAt > 0 ? _nextAt : SRC.lastIndexOf('})();') + '})();'.length
const modSrc = SRC.slice(modStart, modEnd)
if (!modSrc.includes('applyMerged')) {
  console.error('!! 切片没包含 applyMerged，锚点可能失效了')
  process.exit(2)
}
const DEFAULTS_FIXTURE = {
  __global__: { keyboard: { a: 'g_a', b: 'g_b' }, gamepad: { a: 9 } },
  nes: { keyboard: { a: 'n_a', x: 'n_x' }, gamepad: { a: 7 } },
}
globalThis.fetch = (u) => {
  if (String(u).indexOf('/defaults') >= 0) {
    return Promise.resolve({ ok: true, json: () => Promise.resolve({ defaults: DEFAULTS_FIXTURE }) })
  }
  return Promise.reject(new Error('unexpected ' + u))
}
globalThis.localStorage = { getItem: () => null, setItem: () => {}, length: 0, key: () => null }
new Function(modSrc)()

const api = globalThis.__arcadeKeyPlatform && true
ok(!!globalThis.__arcadeEffKb, '模块加载后暴露 __arcadeEffKb')
ok(!!globalThis.__arcadeKeyPack, '暴露 __arcadeKeyPack')

async function main() {
  await globalThis.__arcadeLoadKeyDefaults()
  const defs = globalThis.__arcadeKeyDefaults()
  eq(Object.keys(defs).sort(), ['__global__', 'nes'], '站点默认已加载')

  console.log('\n=== C) 有效默认的三层合并 ===')
  globalThis.__arcadeSetKeyPlatform(null)
  let kb = globalThis.__arcadeEffKb()
  ok(kb.a === 'g_a', '全局默认覆盖硬编码 a', kb.a)
  ok(kb.b === 'g_b', '全局默认覆盖硬编码 b', kb.b)
  ok(kb.start === 'enter', '没被默认覆盖的键保留硬编码值', kb.start)
  ok(kb.up === 'up' && kb.r2 === '3', '硬编码键完整', { up: kb.up, r2: kb.r2 })
  ok(Object.keys(kb).length === 14, '有效默认仍是 14 键', Object.keys(kb).length)

  globalThis.__arcadeSetKeyPlatform('nes')
  kb = globalThis.__arcadeEffKb()
  ok(kb.a === 'n_a', '平台默认覆盖全局默认（a）', kb.a)
  ok(kb.b === 'g_b', '平台没设的键继承全局默认（b）', kb.b)
  ok(kb.x === 'n_x', '平台默认生效（x=连发A）', kb.x)
  ok(kb.y === 'a', '平台没设的连发B 继承硬编码', kb.y)

  let gm = globalThis.__arcadeEffGm()
  ok(gm.a === 7, '手柄：平台默认覆盖全局（a=7）', gm.a)
  ok(gm.b === 0, '手柄：未覆盖的键保留硬编码（b=0）', gm.b)

  console.log('\n=== D) 只存改过的键（diff） ===')
  globalThis.__arcadeSetKeyPlatform('nes')
  const full = Object.assign({}, kb, { b: 'MY_B', start: 'MY_START' })
  const diff = globalThis.__arcadeKeyDiff(full, kb)
  eq(Object.keys(diff).sort(), ['b', 'start'], 'diff 只含改过的 2 个键')
  eq(diff, { b: 'MY_B', start: 'MY_START' }, 'diff 内容正确（未改的 a/x 已被剔除）')

  const packed = globalThis.__arcadeKeyPack({ keyboard: full, gamepad: { a: 7, b: 99 }, kbPlayer: 2, portOrder: null, padNativeOnly: true })
  eq(packed.keyboard, { b: 'MY_B', start: 'MY_START' }, 'pack 的 keyboard 是 diff')
  eq(packed.gamepad, { b: 99 }, 'pack 的 gamepad 是 diff（a=7 与默认相同被剔除）')
  ok(packed.kbPlayer === 2, 'pack 保留 kbPlayer（非 diff 字段）', packed.kbPlayer)

  console.log('\n=== E) 平台隔离 ===')
  globalThis.__arcadeSetKeyPlatform('snes')
  const snesKb = globalThis.__arcadeEffKb()
  ok(snesKb.a === 'g_a', '未配默认的平台 → 回落到全局默认', snesKb.a)
  ok(snesKb.x !== 'n_x', '不会串到 nes 的平台默认', snesKb.x)

  console.log('\n=== F) setKeyboard 自动顶掉旧绑定（跑产物里的真实函数） ===')
  globalThis.__arcadeSetKeyPlatform('nes')
  const eSrc = slice('function e(o,l){var u;var _kb={', ',Ke((u=n.value)==null?void 0:u.id,W.value)}')
  const tSrc = slice('function t(o,l){var u;var _gm={', ',Ke((u=n.value)==null?void 0:u.id,W.value)}')

  // new Function('W','n','Ke', ...) 返回的工厂要**先传入闭包依赖**才能拿到可执行函数
  const n = { value: { id: 1 } }
  let saved = null
  const Ke = (uid, v) => { saved = { uid, v } }

  // setKeyboard：把 b 绑成 a 现在用的键 'i' → a 应恢复成平台默认 'n_a'
  const W1 = { value: { keyboard: { a: 'i', b: 'u', x: 'k' } } }
  const setKb = new Function('W', 'n', 'Ke', 'return (' + eSrc + ')')(W1, n, Ke)
  setKb('b', 'i')
  eq(W1.value.keyboard, { a: 'n_a', b: 'i', x: 'k' },
    '键盘：b 占用 i 后，a 自动恢复成平台默认 n_a（不再重复）')
  ok(saved && saved.uid === 1, '去重后仍会触发保存', saved && saved.uid)

  // 不冲突时不应动别的键
  const W2 = { value: { keyboard: { a: 'i', b: 'u', x: 'k' } } }
  const setKb2 = new Function('W', 'n', 'Ke', 'return (' + eSrc + ')')(W2, n, Ke)
  setKb2('y', 'o')
  eq(W2.value.keyboard, { a: 'i', b: 'u', x: 'k', y: 'o' }, '键盘：不冲突时其它键不动')

  // 手柄：把 b 绑成 a 现在用的按钮 1 → a 恢复成手柄默认 7
  const W3 = { value: { gamepad: { a: 1, b: 0 } } }
  const setGm = new Function('W', 'n', 'Ke', 'return (' + tSrc + ')')(W3, n, Ke)
  setGm('b', 1)
  eq(W3.value.gamepad, { a: 7, b: 1 }, '手柄：b 占用按钮 1 后，a 恢复成默认 7')

  console.log('\n=== G) 重复键清理（WASD 的 W 不生效 —— 2026-09-14 真实案例） ===')
  // 清掉夹具默认，让有效默认 = 硬编码 pt，复现线上环境
  const curDefs = globalThis.__arcadeKeyDefaults()
  Object.keys(curDefs).forEach((k) => { delete curDefs[k] })
  globalThis.__arcadeSetKeyPlatform(null)

  // 玩家真实数据：up/down/left/right = w/s/a/d，而硬编码默认里 r='w'、l2='1'
  const REAL_DIFF = {
    up: 'w', down: 's', left: 'a', right: 'd',
    start: '2', select: '1', a: 'k', b: 'j', x: 'i', y: 'u',
    l: 'q', r: 'w', l2: '1', r2: '3',
  }
  const HARD = globalThis.__arcadeEffKb()
  ok(HARD.r === 'w', '前提：硬编码默认里 r 就是 w（冲突根源）', HARD.r)
  ok(HARD.l2 === '1', '前提：硬编码默认里 l2 就是 1', HARD.l2)

  const realFull = Object.assign({}, HARD, REAL_DIFF)
  globalThis.__arcadeDedupe({ keyboard: realFull }, REAL_DIFF, {})
  ok(realFull.up === 'w', '清理后 up 仍是 w（W 能向上）', realFull.up)
  ok(realFull.r === 'nul', '冲突方 r 被置空（不再抢走 w）', realFull.r)
  ok(realFull.select === '1', '玩家真改过的 select=1 保留（没被 l2 顶掉）', realFull.select)
  ok(realFull.l2 === 'nul', '与 select 冲突的 l2 被置空', realFull.l2)
  ok(realFull.down === 's' && realFull.left === 'a' && realFull.right === 'd', '其余方向键不受影响',
    { d: realFull.down, l: realFull.left, r: realFull.right })
  ok(realFull.start === '2' && realFull.a === 'k' && realFull.x === 'i', '动作键不受影响',
    { s: realFull.start, a: realFull.a, x: realFull.x })

  // 清理后再检查不应有残留冲突
  const seen = {}
  const dup = []
  for (const k of ['up', 'down', 'left', 'right', 'a', 'b', 'x', 'y', 'l', 'r', 'l2', 'r2', 'start', 'select']) {
    const v = realFull[k]
    if (!v || v === 'nul') continue
    if (seen[v]) dup.push(seen[v] + '/' + k)
    else seen[v] = k
  }
  eq(dup, [], '清理后没有任何重复绑定')

  // 绑定期：默认键本身就是新值 → 必须置空（老实现会恢复成同一个 w，等于没去重）
  const W4 = { value: { keyboard: Object.assign({}, HARD) } }
  const setKb3 = new Function('W', 'n', 'Ke', 'return (' + eSrc + ')')(W4, n, Ke)
  setKb3('up', 'w')
  ok(W4.value.keyboard.up === 'w', '绑定：up 设为 w', W4.value.keyboard.up)
  ok(W4.value.keyboard.r === 'nul', '绑定：r 的默认就是 w → 直接置空', W4.value.keyboard.r)

  console.log('\n=== H) 手柄自定义必须下发（改 ABXY 没效果 —— 2026-09-14 真实案例） ===')
  const slotsSrc = slice('function __arcadeSlots()', 'return{cfg:cfg,kbPort:0,padPorts:{}}}')
  const HT_FIX = { a: 1, b: 0, x: 3, y: 2, l: 4, r: 5, l2: 6, r2: 7, select: 8, start: 9, up: 12, down: 13, left: 14, right: 15 }
  const JE_FIX = ['up', 'down', 'left', 'right', 'a', 'b', 'x', 'y', 'l', 'r', 'l2', 'r2', 'start', 'select']
    .map((k) => ({ key: k }))
  const mkSlots = () => new Function('Je', 'ht', 'return (' + slotsSrc + ')')(JE_FIX, HT_FIX)

  // 玩家线上真实数据：把 a 换成按钮 2、x 换成 1、y 换成 3（就是调整 ABXY 位置）
  globalThis.__arcadeGamepad = { a: 2, x: 1, y: 3 }
  const slot1 = mkSlots()()
  ok(slot1.cfg['input_player1_a_btn'] === 2, '手柄 a 用玩家设的按钮 2（不是出厂 1）', slot1.cfg['input_player1_a_btn'])
  ok(slot1.cfg['input_player1_x_btn'] === 1, '手柄 x 用玩家设的按钮 1', slot1.cfg['input_player1_x_btn'])
  ok(slot1.cfg['input_player1_y_btn'] === 3, '手柄 y 用玩家设的按钮 3', slot1.cfg['input_player1_y_btn'])
  ok(slot1.cfg['input_player1_b_btn'] === 0, '没改的 b 仍用出厂 0', slot1.cfg['input_player1_b_btn'])
  ok(slot1.cfg['input_player1_start_btn'] === 9, '没改的 start 仍用出厂 9', slot1.cfg['input_player1_start_btn'])
  ok(slot1.cfg['input_player4_a_btn'] === 2, '2P~4P 同样生效', slot1.cfg['input_player4_a_btn'])
  ok(slot1.cfg['input_player1_a'] === 'nul', '手柄端口的键盘绑定保持 nul', slot1.cfg['input_player1_a'])

  // 没有自定义时必须回落到出厂值（不能因为改了代码就全空）
  try { delete globalThis.__arcadeGamepad } catch (e) { globalThis.__arcadeGamepad = undefined }
  const slot2 = mkSlots()()
  ok(slot2.cfg['input_player1_a_btn'] === 1, '无自定义时回落出厂 a=1', slot2.cfg['input_player1_a_btn'])
  ok(slot2.cfg['input_player1_y_btn'] === 2, '无自定义时回落出厂 y=2', slot2.cfg['input_player1_y_btn'])

  console.log('\n=== I) 按钮 0 必须参与去重（0 是合法按钮，不是「没绑定」） ===')
  // 2026-09-14 线上实测：玩家 left=0（自己改的）+ 平台默认 a=0，
  // 修复前第二轮写的是 if(!v)continue，把 0 当成空 → a 被整个跳过 →
  // 两个键同时下发成 input_player{N}_left_btn=0 / _a_btn=0，核心两个都认，
  // 表现为「按 A 键会连带触发左」，而面板上完全看不出来。
  const ded = globalThis.__arcadeDedupeKb
  ok(typeof ded === 'function', '暴露了裸 dedupe（__arcadeDedupeKb）')
  const K14 = ['up', 'down', 'left', 'right', 'a', 'b', 'x', 'y', 'l', 'r', 'l2', 'r2', 'start', 'select']
  const baseGm = { a: 0, b: 2, x: 1, y: 3, l: 4, r: 5, l2: 6, r2: 7, select: 8, start: 9, up: 12, down: 13, left: 14, right: 15 }
  const outGm = ded(Object.assign({}, baseGm, { left: 0 }), baseGm, { left: 0 })
  ok(outGm.left === 0, '玩家改的 left=0 保留（0 不能被当成空）', outGm.left)
  ok(outGm.a === 'nul', '与 left 撞在按钮 0 的 a 被让位（不再也是 0）', outGm.a)

  const gmSeen = {}
  const gmDup = []
  for (const k of K14) {
    const v = outGm[k]
    if (v === undefined || v === null || v === '' || v === 'nul') continue
    if (gmSeen[v] !== undefined) gmDup.push(gmSeen[v] + '/' + k + '=' + v)
    else gmSeen[v] = k
  }
  eq(gmDup, [], '去重后没有任何残留的重复按钮号')

  // 默认键恰好是 0：修复前 if(dv && ...) 会把「默认=0」误判成「没有默认」而直接置空
  const base0 = Object.assign({}, baseGm, { a: 0, b: 0 })
  const out0 = ded(Object.assign({}, base0), base0, {})
  ok(out0.a === 0, '默认键为 0 时仍被当作合法默认（a 保留 0）', out0.a)
  ok(out0.b === 'nul', '同样默认成 0 的 b 被检出并让位（修复前会被静默跳过成重复）', out0.b)

  console.log('\n=== J) 摇杆轴绑定（[patch] axis-bind）===')
  // 面板能把「上/下/左/右」绑到摇杆：值存成 "<±轴号>" 字符串，下发成 input_playerN_<key>_axis
  const axisName = globalThis.__arcadeAxisName
  ok(typeof axisName === 'function', '暴露了 __arcadeAxisName')
  eq(axisName('-1'), '左摇杆↑', 'token -1 → 左摇杆↑')
  eq(axisName('+1'), '左摇杆↓', 'token +1 → 左摇杆↓')
  eq(axisName('-0'), '左摇杆←', 'token -0 → 左摇杆←')
  eq(axisName('+0'), '左摇杆→', 'token +0 → 左摇杆→')
  eq(axisName('-3'), '右摇杆↑', 'token -3 → 右摇杆↑')
  ok(axisName('nul') === null, 'nul/普通字符串不被当成轴', axisName('nul'))
  ok(axisName(12) === null, '数字按钮号不被当成轴', axisName(12))
  eq(globalThis.__arcadeAxisTok('-2'), '-2', '__arcadeAxisTok 认轴 token')
  ok(globalThis.__arcadeAxisTok('nul') === null, '__arcadeAxisTok 拒绝 nul')
  ok(globalThis.__arcadeAxisTok('1') === null, '不带正负号的数字不是合法轴 token（否则会和按钮号混淆）')

  // __arcadeSlots 的下发：数字 → _btn，token → _axis。
  // 它在 [patch] router 块里（不在本测试的切片范围内），所以单独切出来 eval，
  // 只喂它依赖的 Je（键序）和 ht（硬编码默认）。
  const slotsSrcJ = slice('function __arcadeSlots(){', 'return{cfg:cfg,kbPort:0,padPorts:{}}}')
  const slotsFn = new Function('Je', 'ht', slotsSrcJ + '\nreturn __arcadeSlots')(
    K14.map((k) => ({ key: k })), baseGm)

  globalThis.__arcadeGamepad = Object.assign({}, baseGm, {
    b: 11, up: '-1', down: '+1', left: '-0', right: '+0',
  })
  const sc = slotsFn().cfg
  eq(sc.input_player1_up_axis, '-1', 'up 下发 _axis = "-1"（不是 _btn）')
  eq(sc.input_player1_down_axis, '+1', 'down 下发 _axis = "+1"')
  eq(sc.input_player1_left_axis, '-0', 'left 下发 _axis = "-0"')
  eq(sc.input_player1_right_axis, '+0', 'right 下发 _axis = "+0"')
  ok(sc.input_player1_up_btn === undefined, 'up 不再同时下发按钮号（避免按钮+轴双重触发）', sc.input_player1_up_btn)
  eq(sc.input_player1_b_btn, 11, '数字值仍走 _btn（b=11）')
  eq(sc.input_player2_up_axis, '-1', '2P 同样下发（端口 1..4 一致）')
  ok(sc.input_player1_up === 'nul', '键盘槽位仍被显式置 nul', sc.input_player1_up)
  // 'nul' 是字符串，绝不能被正则当成轴 token
  globalThis.__arcadeGamepad = Object.assign({}, baseGm, { up: 'nul' })
  const sc2 = slotsFn().cfg
  ok(sc2.input_player1_up_axis === undefined, "绑定值 'nul' 不会被误判成轴 token", sc2.input_player1_up_axis)
  ok(sc2.input_player1_up_btn === undefined, "'nul' 时该键两个都不下发（= 未绑定）")

  console.log('\n================================')
  console.log(pass + ' PASS / ' + fail + ' FAIL')
  process.exit(fail ? 1 : 0)
}

main().catch((e) => { console.error(e); process.exit(1) })
