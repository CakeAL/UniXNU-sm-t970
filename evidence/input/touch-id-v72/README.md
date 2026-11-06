# T970 触控身份探针 v72

以 v69 为基线，启用 `t970-touch-bus-report=3`。仅在 SE5 已停且两个 GPIO 都处于 v70 观测的输入下拉配置时操作。暂时取消下拉，只有 SDA/SCL 两线都读高才用开漏方式向 `0x49` 发送 `0x22` 并重复起始，读取五字节后停止。超时有界。GPIO12=SDA、GPIO13=SCL 来自 QUP 通用线序推定，尚无本板应答来验证。返回时恢复 GPIO 控制和输出锁存位。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers \
  --output out/data-bringup/touch-id-v72-build
python3.14 evidence/display/hello-black-v64/prepare.py --touch-id
```

宿主模拟验证了组合读、最终 NACK、STOP，以及地址拒绝、仲裁失败和时钟超时。内核预链接、最终 FAT 回读通过。实机 `idle=0 stage=idle err=none n=0 stop=0 restore=1`。两线都低，探针没有发起 I²C 请求。没有测到 ACK 或芯片 ID，也没有直接测量电源轨。详见 `device-result.json`。
