# Docker 运行说明（urban-facade-color）

## 1) 构建并启动（推荐：Compose）

在项目根目录运行：

```bash
docker compose up --build
```

- FastAPI: http://localhost:8000
- Gradio: http://localhost:7860

## 2) 测试接口

```bash
curl -X POST "http://localhost:8000/analyze" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@images/15641.jpg"
```

## 3) 常见问题

### (A) mmcv/mmseg 安装失败
OpenMMLab 依赖在不同平台/版本组合上较敏感。
如果 build 失败，把错误日志发我，我会根据日志把 `requirements.docker.txt` 精确 pin 到可用的版本组合。

### (B) 想用 GPU/CUDA
目前 Dockerfile 是 CPU 版。若你要用 NVIDIA GPU，需要：
- NVIDIA 驱动 + nvidia-container-toolkit
- 改用 CUDA base image（例如 pytorch/pytorch:*-cuda*）
- docker-compose 加 `deploy`/`--gpus all`

我可以给你出一份 CUDA 版 Dockerfile/compose。
