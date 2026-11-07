# 提案：账户管理与权限边界

## Why

账户与角色已经落库（`users` 表 + bcrypt + JWT，角色分 `admin / engineer`），但**没有任何账户生命周期管理**：

- 管理员只能使用首次启动写入的 `admin / user` 两个种子账户，无法新增、停用、重置密码或删除账户；
- 普通用户无法修改自己的邮箱和密码；
- 侧边栏早已预留「用户管理」入口（`/admin/users`），但路由和页面都不存在，点击无反应；
- 账户的增删改只能改代码或直接操作数据库，缺少可审计、可交接的管理路径。

本次补齐个人账户设置与管理员用户管理，并明确"谁能改谁、什么情况不能删"的权限边界。

## What Changes

- **个人账户设置**
  - `PUT /api/auth/me`：修改自己的邮箱
  - `POST /api/auth/change-password`：校验当前密码后修改密码；新密码至少 6 位，且不能与当前密码相同
- **管理员用户管理**（仅 `admin`）
  - `GET /api/users?search=&page=&pageSize=`：分页、按用户名/邮箱搜索
  - `POST /api/users`：新建账户（用户名唯一、初始密码、邮箱、角色）
  - `PATCH /api/users/{id}`：修改邮箱、角色、启用状态
  - `POST /api/users/{id}/password`：重置指定账户密码
  - `DELETE /api/users/{id}`：删除账户
- **权限与保护规则**
  - 非管理员访问管理接口返回 403
  - 不能修改自己的角色，不能停用或删除自己
  - 至少保留一个启用状态的管理员
  - 已有项目或仿真任务的账户不允许删除，提示改为停用，避免历史数据失去归属
  - 停用后立即无法登录；鉴权每次从数据库读取角色与启用状态，变更下一次请求即生效
- **前端**
  - 新增 `/account` 账户设置页：基本信息（用户名/角色只读、邮箱可改）+ 修改密码
  - 新增 `/admin/users` 用户管理页：搜索、分页、新建、编辑、重置密码、删除；编辑自己时角色与启用开关禁用
  - 侧边栏新增「账户设置」，原有「用户管理」入口接通；顶栏改为用户下拉菜单（账户设置 / 退出登录）
  - 路由增加 `requiresAdmin` 守卫；进入布局时同步一次 `/auth/me`，角色被管理员修改后菜单随之更新
- **数据模型**：不新增表，复用 `users`；密码继续使用 bcrypt，不引入外部身份服务

## Capabilities

### New Capabilities

- `account-management`：定义账户自助管理、管理员账户生命周期、角色与启用状态、以及"不能锁死系统/不能丢历史数据"的保护边界。

### Modified Capabilities

（无。`persistence` 只负责 `users` 表的存储与恢复；账户管理是新增的行为契约，不改动既有要求。）

## Impact

**后端**
- 新增 `app/api/routes/users.py`；`auth.py` 增加个人资料与改密接口；`main.py` 注册路由
- `repositories/users.py` 增加分页查询、管理员计数、关联数据检查、删除
- `models/schemas.py` 增加账户请求模型
- 无数据库迁移（`users` 表结构不变）

**前端**
- 新增 `views/AccountView.vue`、`views/AdminUsers.vue`、`api/users.ts`
- `api/auth.ts`、`stores/userStore.ts`、`router/index.ts`、`components/layout/AppLayout.vue` 同步扩展

**验证与文档**
- 新增 `scripts/verify_accounts.py`（24 项断言）并更新 README「账户与权限」

**兼容性**
- 仅新增接口与页面；登录响应与 `/api/auth/me` 额外返回 `isActive / createdAt / updatedAt`，向后兼容
- 已签发的 JWT 不含密码信息，修改密码不会使其立即失效（无状态令牌的已知取舍，见 design）
