# 示例文档：Docker 部署笔记

## 什么是 Docker

Docker 是一种容器化技术，可以把应用连同它的运行环境一起打包成镜像（Image），
运行镜像得到容器（Container）。容器之间相互隔离，但又共享宿主机的操作系统内核，
因此比虚拟机更轻量、启动更快。

## Dockerfile 基础

Dockerfile 是构建镜像的说明书，常见的指令包括：

- FROM：指定基础镜像；
- COPY：把文件复制进镜像；
- RUN：构建时执行的命令（如安装依赖）；
- EXPOSE：声明容器监听的端口；
- CMD：容器启动时执行的默认命令。

一个简单的 Python 服务 Dockerfile 通常是：FROM python:3.12-slim，
然后 COPY requirements.txt 并 RUN pip install，最后 CMD 启动 uvicorn。

## docker compose 的作用

docker compose 用一份 YAML 文件（docker-compose.yml）定义多个服务，
一条命令 `docker compose up --build` 就能把整个应用栈（后端、前端、数据库）
一起构建并启动，服务之间通过服务名互相访问。适合本地开发与单机部署。

## 部署上线的基本流程

1. 写 Dockerfile 把每个服务镜像化；
2. 用 docker compose 编排所有服务；
3. 把镜像推到云服务器（或直接在服务器上 build）；
4. 配置反向代理（Nginx）与 HTTPS 证书，开放公网端口；
5. 用 docker compose logs 查看日志，docker compose down 停止服务。
