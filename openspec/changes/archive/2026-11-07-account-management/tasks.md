# Tasks

> 实现已随"增加账户管理功能"完成并通过验证；本清单用于留痕与复核。验证环境为 `github_HVAC`（Python 3.12）与 `vue-tsc`。

## 1. 后端接口与校验

- [x] 1.1 `models/schemas.py` 增加账户请求模型：`UserCreate`（用户名/密码/邮箱/角色）、`UserUpdate`（邮箱/角色/启用）、`ProfileUpdate`、`PasswordChange`、`PasswordReset`；验证：`openspec` 变更外运行 `python -c "from app.models.schemas import UserCreate"` 可导入，非法角色返回 422
- [x] 1.2 `repositories/users.py` 增加分页/检索、启用管理员计数、关联数据检查、删除；验证：`scripts/verify_accounts.py` 中列表、计数、删除保护断言通过
- [x] 1.3 `api/routes/auth.py` 增加 `PUT /api/auth/me` 与 `POST /api/auth/change-password`（校验当前密码、至少 6 位、不得与旧密码相同）；验证：错误当前密码返回 400，成功后旧密码登录 401、新密码登录 200
- [x] 1.4 新增 `api/routes/users.py`：`GET /api/users` 分页+搜索、`POST /api/users` 创建（用户名唯一、密码≥6）；验证：创建返回 201，重复用户名 409
- [x] 1.5 `PATCH /api/users/{id}`：修改邮箱/角色/启用状态，禁止改自己角色或停用自己，禁止移除最后一个启用管理员；验证：自我操作返回 400，正常修改 200
- [x] 1.6 `POST /api/users/{id}/password`：管理员重置密码；验证：重置后新密码登录 200、旧密码 401
- [x] 1.7 `DELETE /api/users/{id}`：禁止删除自己/最后一个管理员；有项目或仿真任务的账户返回 409 并提示改为停用；验证：无关联账户删除 200、有关联账户 409
- [x] 1.8 `main.py` 注册 users 路由；验证：`GET /api/users` 未登录 401、工程师 403、管理员 200

## 2. 前端账户界面

- [x] 2.1 `api/users.ts` 与 `api/auth.ts` 补齐类型与调用；`stores/userStore.ts` 增加 `updateUser`；验证：`vue-tsc --noEmit` 零错误
- [x] 2.2 新增 `views/AccountView.vue`：基本信息（用户名/角色只读、邮箱可改）+ 修改密码；验证：改邮箱后 `/auth/me` 返回新值，改密后新密码可登录
- [x] 2.3 新增 `views/AdminUsers.vue`：搜索、分页、新建、编辑、重置密码、删除；编辑自己时角色/启用禁用；验证：页面操作与接口返回一致
- [x] 2.4 `router/index.ts` 增加 `/account`、`/admin/users` 与 `requiresAdmin` 守卫；验证：工程师直接访问 `/admin/users` 被重定向首页
- [x] 2.5 `components/layout/AppLayout.vue` 增加「账户设置」菜单、顶栏用户下拉、进入布局同步 `/auth/me`；验证：管理员角色被修改后菜单随下一次进入布局更新

## 3. 权限与安全边界

- [x] 3.1 非管理员访问任何 `/api/users` 接口返回 403；验证：`verify_accounts.py`「普通用户不能查看账户列表/新建账户」
- [x] 3.2 管理员不能修改自己的角色、停用自己、删除自己；验证：三种操作分别返回 400
- [x] 3.3 至少保留一个启用管理员；验证：代码检查分支覆盖，配合 3.2 的自我保护形成闭环
- [x] 3.4 有项目或仿真任务的账户禁止删除；验证：`verify_accounts.py`「有项目/任务的账户不允许删除」
- [x] 3.5 停用即时生效：登录立即 401，已签发令牌在下一次请求被拒绝；验证：`verify_accounts.py`「停用后无法登录」，鉴权每次读库
- [x] 3.6 密码不以明文/哈希出现在响应；验证：登录响应与账户列表均无密码字段

## 4. 文档与验证

- [x] 4.1 README 新增「八、账户与权限」，记录接口、保护规则与自检命令；验证：按文档命令可跑通
- [x] 4.2 新增 `scripts/verify_accounts.py`（24 项断言，临时库）；验证：`python scripts/verify_accounts.py` 退出码 0
- [x] 4.3 持久化回归：`python scripts/verify_persistence.py`；验证：59/59 断言通过
- [x] 4.4 前端类型检查：`vue-tsc --noEmit -p tsconfig.app.json`；验证：退出码 0
- [x] 4.5 真实 HTTP 联调：登录、创建、停用、重置、改密、删除全链路；验证：各状态码与预期一致（201/200/401/403/400/409）

## Workflow follow-up

- 主规格已同步（`openspec/specs/account-management/spec.md`）。
- 评审通过后归档本 change；若后续需要"强制下线"或审计日志，另开 change（见 design 的 Open Questions）。
