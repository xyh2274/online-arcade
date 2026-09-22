/*
 * test_turbo.js —— 验证 [patch] turbo 的核心逻辑，全部从「已发布的产物」里切出真实函数来跑。
 *
 * 断言五件事：
 *   A. 键位池 Je **不含** turboA/turboB（回归守卫），但含 a/b/x/y
 *   B. pt / ht 同上；默认键位不与已有键位冲突
 *   C. __arcadeSlots() 写出的 cfg 包含 x/y，且不含任何 turbo 键
 *   D. __arcadeCoreOptions() 只对红白机家族下发 fceumm_turbo_enable，
 *      并且 localStorage['arcade-turbo']==='0' 时不下发
 *   E. 平台数组给红白机声明了 x/y，buttonLabels 把它们标成「连发A/连发B」
 *
 * ⚠ 2026-09-14 修正记录见 A 段注释：连发键 = RetroPad 的 X / Y，不是新造的键。
 */
const fs = require('fs');
const path = require('path');

const DIR = __dirname;
const PLAYER = path.join(DIR, 'Player-BwKb4RpM.js');
const PLATFORMS = path.join(DIR, 'platforms-remote.js');

const psrc = fs.readFileSync(PLAYER, 'utf8');
const tsrc = fs.readFileSync(PLATFORMS, 'utf8');

let pass = 0, fail = 0;
function ok(name, cond, extra) {
  if (cond) { pass++; console.log('PASS  ' + name + (extra ? '  ' + extra : '')); }
  else { fail++; console.log('FAIL  ' + name + (extra ? '  ' + extra : '')); }
}
function cut(from, to, src) {
  src = src || psrc;
  const i = src.indexOf(from);
  if (i < 0) throw new Error('锚点起点缺失: ' + from);
  const j = src.indexOf(to, i + from.length);
  if (j < 0) throw new Error('锚点终点缺失: ' + to);
  return src.slice(i, j);
}

/* ---------- 夹具 ---------- */
const store = {}; // 模拟 localStorage
globalThis.localStorage = {
  _d: store,
  getItem(k) { return k in store ? store[k] : null; },
  setItem(k, v) { store[k] = String(v); },
  removeItem(k) { delete store[k]; },
};
globalThis.console = console;

/* ---------- A. 键位池 Je ----------
 * 2026-09-14 修正：第一版往 Je 里塞了 turboA / turboB 两个**凭空发明**的逻辑键，
 * 面板多出两行「连发A/连发B」显示默认 c/v，但 RetroArch 只认固定的 16 个逻辑键
 * （up/down/left/right/a/b/x/y/l/r/l2/r2/l3/r3/start/select），
 * input_player1_turboA 这种名字会被静默忽略 → 面板显示的键跟实际生效的键对不上。
 * 真相（libretro-fceumm src/drivers/libretro/libretro.c）：
 *     bindmap  = { JOYPAD_A→JOY_A, JOYPAD_B→JOY_B, ... }
 *     turbomap = { JOYPAD_X→JOY_A, JOYPAD_Y→JOY_B }   // X=连发A、Y=连发B
 * 所以红白机的 4 个动作键就是既有的 a / b / x / y，一个都不用新造。 */
console.log('=== A) 键位池 Je：不含假连发键，且含 a/b/x/y ===');
const jeSrc = cut('Je=[{key:"up"', '],pt={');
const Je = new Function(jeSrc + ']; return Je;')();
const keys = Je.map(r => r.key);
ok('Je 不含 turboA（回归守卫）', !keys.includes('turboA'));
ok('Je 不含 turboB（回归守卫）', !keys.includes('turboB'));
ok('Je 无 group==="turbo" 的行（回归守卫）', !Je.some(r => r.group === 'turbo'));
ok('Je 含 a / b / x / y（红白机 4 键就靠它们）',
   ['a', 'b', 'x', 'y'].every(k => keys.includes(k)), JSON.stringify(keys));
ok('Je 无重复 key', new Set(keys).size === keys.length);

/* ---------- B. 默认键位 pt / ht ---------- */
console.log('\n=== B) pt / ht 默认真实键位 ===');
const ptSrc = cut('pt={up:"up"', ',Kt={');
const pt = new Function(ptSrc + '; return pt;')();
const htSrc = cut('ht={a:1', '};function __arcadePorts');
const ht = new Function(htSrc + '}; return ht;')();
ok('pt 不含 turboA/turboB（回归守卫）', !('turboA' in pt) && !('turboB' in pt));
ok('ht 不含 turboA/turboB（回归守卫）', !('turboA' in ht) && !('turboB' in ht));
ok('pt 有 x / y 键位', typeof pt.x === 'string' && typeof pt.y === 'string',
   'x=' + pt.x + ' y=' + pt.y);
ok('ht 有 x / y 按钮号', typeof ht.x === 'number' && typeof ht.y === 'number',
   'x=' + ht.x + ' y=' + ht.y);

/* 键盘：连发改绑的键不能撞上已有键位（否则按一下同时触发两个动作） */
const ptVals = Object.values(pt).filter(v => typeof v === 'string' && v !== 'nul');
ok('键盘键位无冲突', new Set(ptVals).size === ptVals.length,
   '重复=' + JSON.stringify(ptVals.filter((v, i) => ptVals.indexOf(v) !== i)));
/* 手柄：按钮号不能撞 */
const htVals = Object.values(ht).filter(v => typeof v === 'number');
ok('手柄按钮号无冲突', new Set(htVals).size === htVals.length,
   '重复=' + JSON.stringify(htVals.filter((v, i) => htVals.indexOf(v) !== i)));
ok('手柄 x 落在合法范围 0..16', ht.x >= 0 && ht.x <= 16);
ok('手柄 y 落在合法范围 0..16', ht.y >= 0 && ht.y <= 16);

/* ---------- C. __arcadeSlots 写出的 cfg ---------- */
console.log('\n=== C) __arcadeSlots() 的 cfg 含 x/y（红白机连发键） ===');
const slotsSrc = cut('function __arcadeSlots()', 'var psPeers=');
const slotsFactory = new Function('Je', 'ht', slotsSrc + '; return __arcadeSlots;');
const slots = slotsFactory(Je, ht);
const RP = slots();
const cfgKeys = Object.keys(RP.cfg);
ok('cfg 有 input_player1_x', cfgKeys.includes('input_player1_x'));
ok('cfg 有 input_player1_y', cfgKeys.includes('input_player1_y'));
ok('4 个玩家都写了 x', [1, 2, 3, 4].every(p => cfgKeys.includes('input_player' + p + '_x')));
ok('键盘 x/y 通道为 nul（路由器运行期接管）',
   RP.cfg.input_player1_x === 'nul' && RP.cfg.input_player1_y === 'nul');
ok('cfg 不含任何 turboA/turboB（回归守卫）',
   !cfgKeys.some(k => /turboA|turboB/.test(k)),
   JSON.stringify(cfgKeys.filter(k => /turbo/.test(k))));
ok('手柄 x 写了 _btn', RP.cfg.input_player1_x_btn === ht.x,
   'got=' + RP.cfg.input_player1_x_btn);
ok('手柄 y 写了 _btn', RP.cfg.input_player3_y_btn === ht.y,
   'got=' + RP.cfg.input_player3_y_btn);
/* 不许出现 -1（会让 RetroArch 内核越界黑屏） */
const negIdx = cfgKeys.filter(k => k.endsWith('_joypad_index') && RP.cfg[k] < 0);
ok('无 joypad_index=-1', negIdx.length === 0, JSON.stringify(negIdx));

/* ---------- D. __arcadeCoreOptions ---------- */
console.log('\n=== D) __arcadeCoreOptions() 平台分支 ===');
const coreSrc = cut('function __arcadeTurboOn()', 'function __arcadeSlots()');
const coreFactory = new Function('localStorage', coreSrc + '; return {__arcadeCoreOptions,__arcadeTurboOn};');
const core = coreFactory(globalThis.localStorage);

const nesOpt = core.__arcadeCoreOptions('nes');
ok('nes → 下发 fceumm_turbo_enable', nesOpt.fceumm_turbo_enable === 'Both',
   JSON.stringify(nesOpt));
const fcOpt = core.__arcadeCoreOptions('famicom');
ok('famicom → 下发', fcOpt.fceumm_turbo_enable === 'Both');
const fdsOpt = core.__arcadeCoreOptions('fds');
ok('fds → 下发', fdsOpt.fceumm_turbo_enable === 'Both');
const snesOpt = core.__arcadeCoreOptions('snes');
ok('snes → 不下发（空对象）', Object.keys(snesOpt).length === 0, JSON.stringify(snesOpt));
const arcOpt = core.__arcadeCoreOptions('arcade');
ok('arcade → 不下发', Object.keys(arcOpt).length === 0, JSON.stringify(arcOpt));
const nilOpt = core.__arcadeCoreOptions(null);
ok('null 平台不炸、不下发', Object.keys(nilOpt).length === 0, JSON.stringify(nilOpt));

/* 运行期开关 */
store['arcade-turbo'] = '0';
const offOpt = core.__arcadeCoreOptions('nes');
ok("localStorage['arcade-turbo']='0' → nes 也不下发", Object.keys(offOpt).length === 0,
   JSON.stringify(offOpt));
ok('__arcadeTurboOn() 反映开关', core.__arcadeTurboOn() === false);
delete store['arcade-turbo'];
ok('移除开关后恢复下发', Object.keys(core.__arcadeCoreOptions('nes')).length > 0);

/* ---------- E. 平台声明含连发（否则面板会把行过滤掉） ---------- */
console.log('\n=== E) 平台按键声明 ===');
/* 平台文件是 ESM，这里只做文本级断言（避免 import 副作用） */
const _i = tsrc.indexOf('s=[...e,"a"');
const _j = tsrc.indexOf('],o=[', _i);
if (_i < 0 || _j < 0) throw new Error('平台锚点缺失');
const platSrc = tsrc.slice(_i, _j) + ']';
ok('红白机声明含 x（连发A）', /"a","b","x","y"/.test(platSrc), platSrc);
ok('红白机声明含 y（连发B）', /"a","b","x","y"/.test(platSrc));
ok('红白机声明不含 turboA/turboB（回归守卫）', !/turboA|turboB/.test(platSrc));
ok('平台文件有 [patch] turbo 标记', tsrc.includes('[patch] turbo'));
/* 连发键的显示名：nes / famicom / fds 必须把 x/y 标成「X-连发A / Y-连发B」
   （加 X/Y 前缀是为了和手柄按键对应，玩家一眼能对上） */
for (const p of ['nes', 'famicom', 'fds']) {
  const m = new RegExp(p + ':\\{x:"([^"]+)",y:"([^"]+)"\\}').exec(tsrc);
  ok(p + ' 的 x/y 显示名为 X-连发A/Y-连发B', !!m && m[1] === 'X-连发A' && m[2] === 'Y-连发B',
     m ? m[0] : '未找到');
}
/* 其它平台不该被误加连发标签。
   注意：arcade 的**原有 6 项**必须逐字不变；末尾的 l2/r2 是后来 [patch] combo（LT-双手 / RT-双腿）
   有意追加的（街机面板要出现 LT/RT 两行），不算 turbo 的改动。 */
ok('arcade 的原有 6 个标签逐字未变', tsrc.includes('arcade:{a:"B",b:"A",x:"D",y:"C",l:"E",r:"F",'));
ok('arcade 的 LT/RT 标签来自 [patch] combo', tsrc.includes('l2:"LT-双手",r2:"RT-双腿"}'));
ok('arcade 按键池含 l2/r2（[patch] combo）',
   tsrc.includes('f={arcade:[...e,"a","b","x","y","l","r",/*[patch] combo*/"l2","r2","start","select"],'));
/* 其它平台的数组必须保持原样（不许被误加） */
ok('SNES(n) 未被改动', tsrc.includes('n=[...e,"a","b","x","y","l","r","start","select"]'));
ok('PSX(c) 未被改动', tsrc.includes('c=[...e,"a","b","x","y","l","r","l2","r2","start","select"]'));
ok('SMS(l) 未被改动', tsrc.includes('l=[...e,"a","b","start"]'));

/* ---------- F. 回归守卫：数据字面量必须自成闭合 ----------
 * 2026-09-14 真实踩到（且第一版诊断是错的）：
 *   `test_port_assign.js` 用 slice(from,to) 切 pt 字面量，slice 含终点，
 *   去掉尾部的 ",Kt={" 后**忘了补回 `}`** → `pt={...turboB:"v"` 未闭合 →
 *   SyntaxError: Unexpected end of input。
 *   当时的报错行恰好指在 `/*[patch] turbo*​/` 上，一度误判为「注释被当成
 *   正则字面量」。实测 `var o={a:1,斜杠星号x星号斜杠b:2}` 完全合法，注释无罪。
 *   所以这里锁定真正的不变量：切开后的字面量必须是完整可解析的表达式。 */
console.log('\n=== F) 数据字面量完整性守卫 ===');
for (const [name, expr] of [
  ['Je', jeSrc + ']; return Je;'],
  ['pt', ptSrc + '; return pt;'],
  ['ht', htSrc + '}; return ht;'],
]) {
  let val = null, err = null;
  try { val = new Function(expr)(); } catch (e) { err = e.message; }
  ok(name + ' 字面量可解析且非空', err === null && val && Object.keys(val).length > 0,
     err ? err : 'keys=' + Object.keys(val).length);
}
/* ⛔ 回归守卫：不许再把 turboA / turboB 塞进这两张默认表。
 * 它们是 RetroArch 不认识的逻辑键，写进去只会让「面板显示的键」和「实际生效的键」对不上。 */
ok('pt 不含 turboA/turboB', !('turboA' in pt) && !('turboB' in pt));
ok('ht 不含 turboA/turboB', !('turboA' in ht) && !('turboB' in ht));
/* 反过来，红白机 4 键依赖的 a/b/x/y 必须在两张表里都在 */
ok('pt/ht 都含 a/b/x/y',
   ['a', 'b', 'x', 'y'].every(k => k in pt && k in ht));

/* ---------- G. 摇杆当方向键（analog_dpad_mode=3） ----------
 * 2026-09-14 用户报障：「nes 不识别摇杆，方向键只识别按键方向键」。
 * 根因：默认 Cn 里是 input_playerN_analog_dpad_mode:1 = "Left Analog"（非 forced），
 * 而 RetroArch input_driver.c 里 1 会在核心声明要模拟输入时被**静默降级成 None**：
 *     case ANALOG_DPAD_LSTICK: if (input_driver_analog_requested) = ANALOG_DPAD_NONE;
 * FCEUmm 为光枪/麦克风声明 ANALOG 能力 → 摇杆失灵，只剩十字键。改成 3（Forced）。 */
console.log('\n=== G) 摇杆→方向键（analog_dpad_mode） ===');

/* 从产物里切出「开关 + 平台判定 + 生成器」三段，显式注入 localStorage 后求值 */
const adSrcFull = psrc.slice(
  psrc.indexOf('function __arcadeAnalogDpadOn()'),
  psrc.indexOf('globalThis.__arcadeAnalogDpadCfg=__arcadeAnalogDpadCfg;')
);
ok('切到 analog-dpad 实现', adSrcFull.length > 200, adSrcFull.length + ' chars');
const adF = new Function('localStorage',
  adSrcFull + '; return {on:__arcadeAnalogDpadOn,isDig:__arcadeIsDigitalOnly,cfg:__arcadeAnalogDpadCfg};'
)(globalThis.localStorage);

ok('nes → analog_dpad_mode=3', adF.cfg('nes')['input_player1_analog_dpad_mode'] === 3,
   JSON.stringify(adF.cfg('nes')));
ok('4 个端口全部下发', [1, 2, 3, 4].every(p => adF.cfg('nes')['input_player' + p + '_analog_dpad_mode'] === 3));
ok('值必须是 3（Forced）而不是 1', adF.cfg('nes')['input_player1_analog_dpad_mode'] !== 1);
for (const p of ['famicom', 'fds', 'gb', 'gbc', 'gba', 'snes', 'sfc', 'megadrive', 'arcade', 'sms']) {
  ok(p + ' → 下发', Object.keys(adF.cfg(p)).length === 4, JSON.stringify(adF.cfg(p)));
}
/* ⛔ 真需要模拟摇杆的平台绝不能下发（否则摇杆模拟值被清零） */
for (const p of ['psx', 'n64', 'psp', 'dreamcast', 'saturn', 'nds']) {
  ok(p + ' → 不下发（保护模拟摇杆）', Object.keys(adF.cfg(p)).length === 0,
     JSON.stringify(adF.cfg(p)));
}
ok('null 平台不炸、不下发', Object.keys(adF.cfg(null)).length === 0);
ok('未知平台不下发（保守）', Object.keys(adF.cfg('someunknownsystem')).length === 0);

store['arcade-analog-dpad'] = '0';
ok("localStorage['arcade-analog-dpad']='0' → 不下发", Object.keys(adF.cfg('nes')).length === 0);
ok('__arcadeAnalogDpadOn() 反映开关', adF.on() === false);
delete store['arcade-analog-dpad'];
ok('移除开关后恢复下发', Object.keys(adF.cfg('nes')).length === 4);

/* 覆盖必须发生在 Cn 默认值之后，否则 1 会盖掉我们的 3。
   注意：要看**调用点**而不是定义点（定义在文件前部，会误导）。 */
const cnIdx = psrc.indexOf('input_player1_analog_dpad_mode:1');
ok('默认 Cn 里确实是 1（说明我们没改默认表）', cnIdx > 0);
const rcMerge = psrc.indexOf('for(var kk in RP.cfg)rc[kk]=RP.cfg[kk];');
const adCall = psrc.indexOf('var adc=globalThis.__arcadeAnalogDpadCfg');
ok('覆盖调用点在 RP.cfg 合并之后', adCall > rcMerge && rcMerge > 0,
   'adCall=' + adCall + ' rcMerge=' + rcMerge);
const adWrite = psrc.indexOf('for(var q2 in ad)rc[q2]=ad[q2];');
ok('覆盖确实写进 rc（不是只算了没用）', adWrite > adCall && (adWrite - adCall) < 300);
ok('覆盖晚于 Cn 展开（保证 3 能盖掉 1）', adCall > cnIdx, 'adCall=' + adCall + ' cnIdx=' + cnIdx);

/* ---------- 汇总 ---------- */
console.log('\n=========================');
console.log((fail === 0 ? 'ALL PASS' : 'HAS FAILURES') + ' (' + pass + ' 断言, ' + fail + ' 失败)');
process.exit(fail === 0 ? 0 : 1);
