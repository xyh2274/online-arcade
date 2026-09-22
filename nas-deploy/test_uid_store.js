/* 单元测试：[patch] uid-store —— `__arcadeKeymapApi.uid()` 必须能解析出真实用户 id。
 *
 * 背景（用户报告「拳皇2002 改手柄键位保存+重启后还是旧值」的真根因）：
 *   `ai()` 原来只从 localStorage 找用户 id（arcade-user / user / auth-user / arcade:user / uid / userId），
 *   但本应用登录态是 cookie + GET /api/auth/me，**从不往 localStorage 写用户对象** →
 *   uid 恒 null → `__arcadeSyncPlatformKeys()` 永远走「未登录」分支、从不拉服务端键位，
 *   且 `applyMerged()` 读本机缓存时用的是 `input-mapping:guest`（面板存的是 `input-mapping:<真uid>`）→ 两边 key 对不上。
 *
 * 与既有测试同一思路：从**已打补丁的产物**里原样切出那段 IIFE 来跑，不重写逻辑。
 * 新增行为：`ai()` 在 localStorage 找不到时，回退问同 chunk 已 import 的 auth store（`Ht()`）。
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

console.log('=== A) 产物里补丁在位 ===')
ok(SRC.includes('/*[patch] uid-store'), '带 [patch] uid-store 标记')
ok(/function ai\(\)\{[\s\S]*?uid-store[\s\S]*?return null\}/.test(SRC), 'uid-store 补丁落在 ai() 内部')
ok(/typeof Ht==="function"/.test(SRC), 'ai() 里有 `typeof Ht==="function"` 守卫')
ok(/\{g as Ht/.test(SRC), '产物确实 import 了 `g as Ht`（auth store）')
ok(/function ai\(\)[\s\S]{0,40}try\{for\(var i=0;i<UK\.length/.test(SRC), 'ai() 原有的 localStorage 探测仍在（向后兼容）')

// 链路：syncPlatformKeys 依赖 uid()，且 uid 取不到时会走「未登录」分支 —— 这正是 bug 的传导路径
ok(/if\(!uid\|\|uid==='guest'\)return loadDefaults\(\)\.then\(function\(\)\{return applyMerged\(null,null\)\}\)/.test(SRC),
  'syncPlatformKeys 未登录分支仍是 applyMerged(null,null)（所以 uid 必须可靠）')

console.log('\n=== B) 切出 keymap-srv IIFE 并喂不同桩 ===')
const A = '(function(){if(globalThis.__arcadeKeymapSrv)return;'
const B = 'inflight:function(){return T}}})();'
const i = SRC.indexOf(A)
const j = SRC.indexOf(B)
if (i < 0 || j < 0) { console.error('!! 切片锚点失效'); process.exit(2) }
const IIFE = SRC.slice(i, j + B.length)
if (!IIFE.includes('uid-store')) { console.error('!! 切出来的 IIFE 不含 uid-store'); process.exit(2) }

const lsOf = (obj) => ({
  getItem: (k) => (Object.prototype.hasOwnProperty.call(obj, k) ? obj[k] : null),
  setItem: () => {}, removeItem: () => {}, length: 0, key: () => null,
})

function loadApi(Ht, ls) {
  delete globalThis.__arcadeKeymapSrv          // 解除 IIFE 的幂等守卫，允许重复加载
  delete globalThis.__arcadeKeymapApi
  globalThis.localStorage = ls
  globalThis.fetch = () => Promise.reject(new Error('unexpected fetch'))
  return new Function('Ht', IIFE + '\nreturn globalThis.__arcadeKeymapApi;')(Ht)
}
const uid = (Ht, lsObj) => loadApi(Ht, lsOf(lsObj)).uid()

const user = (o) => () => ({ user: { value: o } })

console.log('\n--- B1) 回归：老行为（localStorage 优先）---')
ok(uid(undefined, {}) === null, 'localStorage 空 + 没有 store → null')
ok(uid(undefined, { 'arcade-user': JSON.stringify({ id: 7 }) }) === 7, 'arcade-user 里的 id 优先')
ok(uid(user({ id: 42 }), { 'user': JSON.stringify({ id: 9 }) }) === 9, 'localStorage 存在时优先于 store')
ok(uid(undefined, { 'uid': '31' }) === 31, '兜底 key uid（字符串数字转 int）')
ok(uid(undefined, { 'userId': 'abc' }) === 'abc', '兜底 key userId（非数字原样返回）')

console.log('\n--- B2) 新增：localStorage 空时回退 auth store（本次修复）---')
ok(uid(user({ id: 2 }), {}) === 2, 'store 里的 user.id=2 → 2  ← 修复点')
ok(uid(user({ userId: 43 }), {}) === 43, 'store 里的 user.userId 也认')
ok(uid(() => ({ user: { value: { id: 0 } } }), {}) === null,
  'id=0 → null（见下方注释：与下游 !uid 约定一致）')
// 说明：`users.id` 是 SQLite 自增主键，从 1 开始，0 不是合法用户 id；
// 且下游 `__arcadeSyncPlatformKeys` 用 `if(!uid||uid==='guest')` 判匿名 —— uid=0 本来也走不通。
// 所以这里**有意**不把 0 当合法值（若将来真出现 id=0，需要连下游那处一起改成 `uid==null` 才行）。
// ⚠ 对照：这与「按钮号 0 是合法的」是两回事（那是 2026-09-14 修过的另一个 bug），别混。

console.log('\n--- B3) 异常/边界都不能把页面搞崩 ---')
ok(uid(user(null), {}) === null, 'store.user.value = null → null')
ok(uid(user({ username: 'x' }), {}) === null, 'user 上既没 id 也没 userId → null')
ok(uid(() => undefined, {}) === null, 'Ht() 返回 undefined → null')
ok(uid(() => ({}), {}) === null, 'Ht() 返回 {}（无 user）→ null')
ok(uid(42, {}) === null, 'Ht 不是函数（数字）→ null，不抛')
ok(uid(() => { throw new Error('boom') }, {}) === null, 'Ht() 抛异常被吞掉 → null')
ok(uid(user({ id: 2 }), null) === 2, 'localStorage 整个不可用（getItem 抛）时仍能靠 store 拿到 id')
ok((() => {   // localStorage 抛异常 + 无 store → null，不崩
  delete globalThis.__arcadeKeymapSrv
  globalThis.localStorage = { getItem() { throw new Error('denied') }, setItem() {}, length: 0, key: () => null }
  globalThis.fetch = () => Promise.reject(new Error('x'))
  return new Function('Ht', IIFE + '\nreturn globalThis.__arcadeKeymapApi;')(undefined).uid() === null
})(), 'localStorage 抛异常 + 无 store → null')

console.log('\n--- B4) 同 chunk 一致性：面板读的 store 与 uid() 是同一个 ---')
ok(/const\{user:n\}=Ht\(\)/.test(SRC) && /Ke\(\(u=n\.value\)==null\?void 0:u\.id,W\.value\)/.test(SRC),
  '面板 Ke() 用的是 Ht().user.value.id —— 与 uid() 同源')

console.log('\n================================')
console.log(pass + ' PASS / ' + fail + ' FAIL')
process.exit(fail ? 1 : 0)
