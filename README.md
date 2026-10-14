# 喜马拉雅 iOS 去广告 — Loon 插件

给喜马拉雅 FM（App Store 主包 `com.gemd.iting`，当前线上版本 9.5.13）做网络层去广告。

## 先说清楚一件事：iPhone 镜像在这套方案里扮演什么角色

macOS 的 iPhone Mirroring 是一条**显示 + 输入转发**通道：它把 iPhone 的画面投到 Mac，把 Mac 的键盘鼠标转发回去。App 本身仍然运行在 iPhone 上，镜像窗口不提供文件系统访问、不提供进程注入、也不能侧载 IPA。

所以「透过镜像给 App 打补丁」这条思路走不通 —— 但**你并不需要它**。

去广告有两条技术路线：

| 路线 | 前提 | 是否需要镜像 |
|------|------|------|
| 越狱 + Theos Tweak 注入 | 设备已越狱 | 不需要 |
| **网络层拦截（Loon）** | 未越狱，装个 Loon | 只用来在 Mac 上操作手机上的 Loon |

你选的是第二条，也是未越狱环境下唯一能落地的方案。Loon 通过 MitM 解密 HTTPS，在本地把广告请求掐掉或改写成空数据 —— 广告请求根本出不了手机。镜像窗口的作用是让你在 Mac 上直接操作手机里的 Loon，省得两台设备来回切。

## 能力边界（提前说，省得后面踩坑）

- Loon 的规则只有**域名 / IP / URL / 端口 / 协议**维度，**没有 App 维度**。所以域名级拦截是全局的，其他 App 调用同一批广告平台也会一起被拦。插件里 B 区专门标了这个，可以整段关掉。
- 广告如果走 QUIC / HTTP3（UDP），MitM 抓不到也改不了，需要在 Loon 里关掉 QUIC。
- 广告位被拦后 UI 可能留白框 —— 这属于正常现象，改写成「返回空结构」而不是「断连」可以缓解，C 区用的就是这个思路。

## 文件

| 文件 | 用途 |
|------|------|
| `ximalaya-adblock.plugin` | Loon 插件本体，四个分区：A 喜马拉雅自有广告域名 14 条 / A2 埋点采集 2 条 / B 第三方广告平台 22 条 / C 接口级复写 3 条 / D MitM 范围 |
| `CAPTURE.md` | 抓包定位真实广告接口的操作手册 |
| `extract-ad-domains.py` | 把抓包产物（Loon 记录 / mitmproxy / Charles 导出）转成 Loon 规则行，带广告特征打分与业务白名单 |
| `start-server.sh` | 在 Mac 上起 HTTP 服务，让 iPhone 上的 Loon 通过 URL 拉取插件 |

## 安装

**1. 先确认 Loon 的 MitM 证书已安装并信任**

设置 → 通用 → 关于本机 → 证书信任设置 → 打开 Loon 的开关。这一步漏掉，C 区的复写不生效（A 区仍然照常工作）。

**2. 起本地服务**

```bash
./start-server.sh
```

它会打印形如 `http://192.168.31.123:8000/ximalaya-adblock.plugin` 的地址。手机和 Mac 要在同一个 Wi-Fi 下。

**3. iPhone 上导入**

Loon → 插件 → 右上角 + → 从 URL 添加 → 粘贴上面的地址。

或者用 iPhone Mirroring 把 `.plugin` 文件直接拖进手机的「文件」App，再在 Loon 里从本地文件导入。

**4. 打开插件，去喜马拉雅验证**

冷启动一次看开屏广告有没有消失。

## 迭代

改 `ximalaya-adblock.plugin` → Loon 插件详情页下拉刷新 → 重新验证。规则怎么从抓包结果推导，看 `CAPTURE.md`。

---

## 当前覆盖状态

### A 区 · 喜马拉雅自有广告域名（14 条，全部实测存在）

| 域名 | 解析 | HTTP 响应 | 判定 |
|------|------|-----------|------|
| `adse.ximalaya.com` | 101.91.133.96 | 401 `{"msg":"50","ret":50}` | 广告服务 API |
| `ad.ximalaya.com` | 101.72.227.92 | 401 `{"msg":"50","ret":50}` | 广告服务 API |
| `adbehavior.ximalaya.com` | 101.91.134.73 | 401 `{"msg":"50","ret":50}` | 广告行为上报 |
| `adbs.ximalaya.com` | 43.159.108.101 | 401 `{"msg":"50","ret":50}` | 广告后端 |
| `adwbs.ximalaya.com` | 43.159.108.101 | 401 `{"msg":"50","ret":50}` | 广告后端 |
| `adsehera.ximalaya.com` | 43.159.108.101 | 401 `{"msg":"50","ret":50}` | 广告服务 |
| `adx.ximalaya.com` | 43.159.108.101 | 200 tengine 默认页 | 广告交易平台 |
| `adweb.ximalaya.com` | 43.159.108.101 | 200 tengine 默认页 | 广告 H5 |
| `dns.ximalaya.com` | 43.159.108.101 | 200 tengine 默认页 | 广告 SDK DNS 探测 |
| `adse.wsa.ximalaya.com` | 43.159.108.101 | — | 与 adx 同集群 |
| `adbehavior.wsa.ximalaya.com` | 43.159.108.101 | — | 与 adx 同集群 |
| `ad.test.ximalaya.com` | 112.65.211.111 | — | 测试环境 |
| `adse.test.ximalaya.com` | 112.65.211.111 | — | 测试环境 |
| `adweb.test.ximalaya.com` | 10.146.3.14 | — | 测试环境 |

`43.159.108.101` 同时承载 8 个喜马拉雅广告子域，`dns.ximalaya.com` 与它同 IP —— 那是广告 SDK 的 DNS 探测入口，不是系统 DNS 服务，所以 SukkaW 规则集把它归入广告是准确的。

`adsebs.ximalaya.com` 被剔除：dig 返回 NXDOMAIN，域名不存在，写进规则等于空跑。

### A2 区 · 埋点与数据采集（2 条）

`xdcs-collector.ximalaya.com`（403 request forbidden）、`linkeye.ximalaya.com`（404 Apache Tomcat/8.0.47）。拦掉只掉统计上报和推荐画像，不影响播放、下载、登录；如果「猜你喜欢」明显变差，把这两行注释掉即可恢复。

### 有争议、默认未启用

`location.ximalaya.com`（101.91.133.50，200 tengine 默认页）默认**不拦**。它是定位服务，NobyDa / Dlerio 都把它算作广告（用于地域定向），但它同时服务正常的地域内容分发，拦掉可能导致「本地电台」之类按地区推荐的功能异常。插件里那行是注释状态，要试就取消注释，跑一天看地区推荐是否正常。

### B 区 · 第三方广告平台（22 条）

沿用公开规则集，未逐条复核 —— 它们是通用广告域名，与喜马拉雅没有绑定关系。早期版本里那三条穿山甲域名（`pangolin-sdk-toutiao.com`、`pangolin-sdk-toutiao-b.com`、`pglstatp-toutiao.com`）在 8.8.8.8 和 223.5.5.5 上全部 NXDOMAIN，是空跑规则，已换成实测存在的 `pangolin16.sgsnssdk.com` 与 `ad.toutiao.com`。

### C 区已经不是模板了

三条接口级复写来自 [NobyDa/Script](https://github.com/NobyDa/Script) 的公开规则集（原为 Surge / QuantumultX 语法）：

```
^https?:\/\/adse\.ximalaya\.com\/ting\/feed\?appid=     - reject
^https?:\/\/adse\.ximalaya\.com\/ting\/loading\?appid=  - reject
^https?:\/\/adse\.ximalaya\.com\/ting\?appid=           - reject
```

分别命中 `/ting/feed?appid=`（音频流内插广告）、`/ting/loading?appid=`（开屏广告）、`/ting?appid=`（通用广告请求）。

转到 Loon 后写成 `reject_dict(200)`。关键在于 Loon 的 Rewrite **在规则匹配前执行**：这三条先返回 `200 + {}`，App 拿到一个合法但空的响应，静默渲染无广告状态，不会触发重试逻辑；A 区再兜住 adse 域名上未被复写覆盖的其余路径。两者叠加，adse 的任何请求都出不去，而已知广告接口走的是「空数据」而非「连接失败」这条更顺的路。

生效前提是 D 区 MitM 包含 `adse.ximalaya.com`。没解密就退化成 A 区直接断开 —— 效果仍在，只是 App 侧多一次失败重试。

### 还能往哪加

抓包拿到新路径后，照 C 区的形状补一行即可：

```
request if ${url} ~= /^https?:\/\/adse\.ximalaya\.com\/新路径/ then reject_dict(200)
```

`pbpaste | python3 extract-ad-domains.py` 可以把抓包产物转成规则行，带广告特征打分与业务白名单（`xmcdn.com` 音频 CDN、`passport` 登录接口自动放行）。
