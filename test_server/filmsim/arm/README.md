# NX-KS2 阶段 2A：ARM 交叉编译（胶片引擎实机化第一步）

## 目标
把阶段 1（PC 原型）的胶片仿真算法编译成 NX1/NX500（DRIMe5 / Tizen 2.2）能直接运行的原生 ARM 程序。

## 环境与工具链
- **工具链**：Zig 0.13.0（`D:/download/NX-KS2-88/.uploads/zig/zig-windows-x86_64-0.13.0/zig.exe`）
  - Zig 自带交叉编译 + glibc 支持，无需安装 Linux 工具链
- **目标三元组**：`arm-linux-gnueabi.2.15`
  - `arm` = ARMv7（Cortex-A9，NX1/NX500 的 DRIMe5 SoC）
  - `gnueabi` = EABI5 **softfp（软浮点）**——已通过解析 rootfs 库确认（flags 0x05000002，Tizen 2.2 armv7l 惯例）
  - `.2.15` = glibc 版本号，匹配相机 Tizen 2.2 的 glibc（~2.15），保证动态链接兼容
- **系统头/库（sysroot）**：从 `NX1_packages.tar` 提取的 rootfs 开发文件
  - 头文件：`.uploads/nx1_open/rootfs_dev/standard-armv7l/usr/include`
  - 库：`.uploads/nx1_open/rootfs_dev/standard-armv7l/usr/lib`

## 编译
```bash
bash test_server/filmsim/arm/build.sh        # 全部
bash test_server/filmsim/arm/build.sh hello  # 仅验证程序
bash test_server/filmsim/arm/build.sh jpeg   # 仅胶片骨架
```
产物：`test_server/filmsim/arm/out/*.arm`

## 产物
| 文件 | 说明 | 动态依赖 |
|---|---|---|
| `hello.arm` | 工具链/ABI 验证（打印 + 浮点） | libc.so.6 |
| `jpeg_film.arm` | 胶片引擎骨架：JPEG 读 → 3x3 矩阵 → 写回 | libjpeg.so.8（rootfs 自带）+ libc.so.6 |

用法：`jpeg_film <in.jpg> <out.jpg> [m00..m22 共9个矩阵系数]`

## 部署到相机
1. 把 `out/*.arm` + 输入 JPG 复制到 SD 卡（如 `/sdcard/`）
2. 开启相机（autoexec.sh 沙箱环境，参考项目现有脚本体系）
3. 执行：
   ```sh
   chmod +x /sdcard/jpeg_film.arm
   /sdcard/jpeg_film.arm /sdcard/in.JPG /sdcard/out.JPG
   ```
4. 相机 rootfs 自带 libjpeg.so.8（libjpeg-turbo），无需额外部署

## 验证（无真机时）
```bash
python test_server/filmsim/arm/verify_elf.py test_server/filmsim/arm/out/*.arm
```
期望：`machine=40(ARM) | eabi_v5 | flags=0x05000002`（EABI5 softfp）
若有 qemu-arm 可进一步运行验证。

## 后续（阶段 2B）
- 接入完整配方：JSON 解析 + 3D LUT（.cube）+ 颗粒（tint yccMixer 或自实现）
- tint 路线需要 C++ 工具链 + 更多 rootfs 库（libtint-util/libmm-type/libstdc++），本阶段先用 libjpeg-turbo 打通链路
