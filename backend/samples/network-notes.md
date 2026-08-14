# 计算机网络基础

## TCP/IP 分层

TCP/IP 四层模型：应用层、传输层、网络层、网络接口层。
HTTP/HTTPS 属于应用层，TCP/UDP 属于传输层，IP 属于网络层。

## TCP 三次握手与四次挥手

三次握手：SYN → SYN+ACK → ACK，目的是双方确认收发能力。
四次挥手：FIN → ACK → FIN → ACK，因为 TCP 是全双工，要两边各自关闭。
TIME_WAIT 等待 2MSL，保证最后的 ACK 能到达、旧报文不串扰新连接。

## HTTP 与 HTTPS

HTTP 无状态明文；HTTPS 在 TCP 之上加 TLS 层：
证书校验（防冒充）→ 密钥协商（ECDHE 等）→ 对称加密传输（性能好）。
HTTP/1.1 用 keep-alive 复用连接，HTTP/2 多路复用解决队头阻塞。

## 常见状态码

2xx 成功（200 OK）、3xx 重定向（301/302）、4xx 客户端错误（404 找不到、429 限流）、
5xx 服务端错误（500 内部错误、502 网关错误、504 超时）。
