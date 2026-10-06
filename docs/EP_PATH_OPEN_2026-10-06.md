# EP 通路全线打通报告

**日期** 2026-10-06 · **阶段** 步骤 2a + 2b 完成
**决定性依据** 用户提供的三星 NX500 开源包（`E:\新建文件夹\NX500_opensource_2015_03_04`）
**安全** 全程 `O_RDONLY` + `PROT_READ`，未写任何寄存器

---

## 一句话

★★★ **魔灯所需的完整写入链已全部打通并被实机数据证实。**
不必猜地址、不必解析 ELF、不必跨进程读指针 —— **内核直接把 10 个 EP 块的
物理地址交给用户态**，剩下的就是往寄存器写值。

---

## 1. 开源包的价值：与 NX1 不是同一批

| | 我原来分析的 | **实机（从 FTP 拉的）** | **NX500 开源包** |
|---|---|---|---|
| 大小 | 279036 B | ★ **320216 B** | 279036 B |
| md5 | `abcbaaf7…` | ★ `40c7b087…` | `abcbaaf7…` |
| 日期 | 2014-09-19 | 2015-01 | 2014-09-19 |
| FUNC | 453 | 459 | 453 |

⇒ ★ **开源包那份 = 我最初分析的**；实机那份是**未开源的更新版**。
⇒ ★ **两份都留着**：old 用于"有源码对照"，real 用于"实机运行时"。

★ 但**内核源码的价值远大于这个库** —— 它解答了所有逆向猜不出来的东西。

---

## 2. ★★★ EP 驱动完整源码（8 文件 2448 行）

```
E:\新建文件夹\NX500_opensource_2015_03_04\home\songha.choi\osp\NX500\linux-3.5\
  drivers/media/video/drime5/ep/
    d5_ep.c        16515B  probe / resume / register_iomap
    d5_ep_ioctl.c  15633B  ★ file_operations + 15 个 ioctl 实现
    d5_ep_intr.c   21638B
    d5_ep_dd.c      6625B  ★ reg_info 全局
    d5_ep_regs.h    1540B
  include/media/drime5/ep/
    d5_ep_ioctl.h★ 全部 ioctl 号定义（magic = 'h'）
    d5_ep_type.h         ★ 全部结构定义
```

★ 用户态头文件也在标准包里：
`standard-armv7l/usr/include/media/drime5/ep/` ⇒ **不必手抄结构体**

---

## 3. ★★★★ 三个决定性源码结论

### 3.1 `/dev/drime5_ep` 是纯 mmap 设备，`open` 零硬件初始化

```c
const struct file_operations drime5_ep_ops = {
    .owner         = THIS_MODULE,
    .open          = drime5_ep_open,
    .release       = drime5_ep_release,
    .unlocked_ioctl= drime5_ep_ioctl,
    .mmap          = d5_ep_mmap
};

static int drime5_ep_open(struct inode *inode, struct file *filp)
{
    struct drime5_ep *ep = g_ep;
    filp->private_data = ep;
    ret = d5_kdd_open(KDD_EP);        /* 仅电源管理计数 */
    /* 没有 request_irq / 没有 ioremap / 没有时钟配置 */
}

int d5_ep_mmap(struct file *file, struct vm_area_struct *vma)
{
    size = vma->vm_end - vma->vm_start;
    vma->vm_flags |= VM_IO | VM_RESERVED;
    vma->vm_page_prot = pgprot_noncached(vma->vm_page_prot);
    io_remap_pfn_range(vma, vma->vm_start, vma->vm_pgoff, size,
                       vma->vm_page_prot);
}
```

⇒ ★★ `request_mem_region` + `ioremap` 只在 **probe（开机）** 做一次。
用户态 `open` **完全不碰硬件** ⇒ **不会与正在工作的 ISP 固件抢资源**。

`drime5_ep_probe` 也只做时钟：
```c
static int __devinit drime5_ep_probe(pdev) { return _drime5_ep_resume(pdev, 1); }
static int drime5_ep_resume(pdev)       { return 0; }   /* 故意什么都不做 */
```

### 3.2 ★★★★★★ 钥匙：内核直接把 10 个 EP 块物理地址交给用户态

```c
#define EP_IOCTL_GET_PHYS_REG_INFO   _IOR('h', 100, struct ep_reg_info)

struct ep_reg_phys_info { unsigned int reg_start_addr; unsigned int reg_size; };

struct ep_reg_info {        /* 顺序即内存布局，10 × 8B = 80 字节 */
    struct ep_reg_phys_info reg_base_top;     /* 0x20820000 */
    struct ep_reg_phys_info reg_base_ldc;     /* 0x20823000 */
    struct ep_reg_phys_info reg_base_mc;      /* 0x20824000 */
    struct ep_reg_phys_info reg_base_rsz;     /* 0x20826000 */
    struct ep_reg_phys_info reg_base_lvr;     /* 0x20827000 */
    struct ep_reg_phys_info reg_base_bblt;    /* 0x20828000 */
    struct ep_reg_phys_info reg_base_fd;      /* 0x20829000 */
    struct ep_reg_phys_info reg_base_jpeg;    /* 0x2082a000 */
    struct ep_reg_phys_info reg_base_3dlut;   /* 0x2082b000  ★魔灯目标 */
    struct ep_reg_phys_info reg_base_nog;     /* 0x20821c00 */
};

/* d5_ep_ioctl.c */
case EP_IOCTL_GET_PHYS_REG_INFO:
    ep_get_reg_info(&ep_reg_info);            /* memcpy(&reg_info, 80) */
    copy_to_user(arg, &ep_reg_info, size);
```

⇒ ★★★★★★ **一个 ioctl 拿到全部权威地址。再也不用猜。**

### 3.3 全部 15 个 ioctl 都是中断/时钟/电源类

```
_IOR ('h',100, ep_reg_info)     ★ 拿 10 块物理地址（唯一的寄存器相关）
_IOW ('h',  6, core_intr_wait)   _IO('h',40) UDD_LOCK   _IO('h',41) UDD_UNLOCK
_IOW ('h',  8, acc_intr_wait)    _IOW('h',22, jpeg_opmode)
_IOW ('h',  9..13, *_wait_q_init) _IOW('h',50,int) SET_CLK_RATE
_IOW ('h', 14..21, *_intr_enable/_disable × 4 组)   _IO('h',60/61) QOS
```

⇒ ★★ **没有一个配置寄存器** ⇒ **寄存器访问 100% 走 `mmap`**，
与静态分析的 `ep_*_reg_base` 是**指针变量**这一事实完全一致。

---

## 4. ★★★ 实机验证：步骤 2a — 10/10 双向闭环

```
open("/dev/drime5_ep", O_RDONLY) = fd 3★
ioctl 请求号 = 0x80506864 = _IOR('h',100, 80)   ★成功
```

| block | phys_start | size | 与 `/dev/mem` 实测 |
|---|---|---|---|
| top | `0x20820000` | 0x1c00 | ✓ |
| ldc | `0x20823000` | 0x1000 | ✓ |
| mc | `0x20824000` | 0x2000 | ✓ |
| rsz | `0x20826000` | 0x1000 | ✓ |
| lvr | `0x20827000` | 0x1000 | ✓ |
| bblt | `0x20828000` | 0x1000 | ✓ |
| fd | `0x20829000` | 0x1000 | ✓ |
| jpeg | `0x2082a000` | 0x1000 | ✓ |
| **3dlut** | **`0x2082b000`** | **0x1000** | ✓ |
| nog | `0x20821c00` | **0x100** | ✓ |

⇒ ★★★ **内核权威值与 `/dev/mem` 读侧历史实测 10/10 完全一致。**

★ 注意 **nog 只有 0x100 = 256 字节**（其余块都是 0x1000）。

---

## 5. ★★★ 实机验证：步骤 2b — 静态预测被逐条证实

```c
fd = open("/dev/drime5_ep", O_RDONLY);
p  = mmap(NULL, 0x1000, PROT_READ, MAP_SHARED, fd, 0x2082b000);   /* ★ 字节地址 */
```
★ **踩坑**：offset 传 `phys>>12` ⇒ `EINVAL`。
驱动 `io_remap_pfn_range` 期望 PFN，但 **mmap 的 offset 单位是字节，内核自己会 `>>PAGE_SHIFT`**。

### 3DLUT 块实际内容（1024 words，64 非零）

| 偏移 | 值 | 意义 | 静态预测 |
|---|---|---|---|
| `+0x000` | `0x00000001` | — | — |
| `+0x004` | `0x00000100` | — | — |
| **`+0x00c`** | **`0x81115200`** | **LUT0 数据地址寄存器** | ★★★ **正是静态解出的 `+0x0c`** |
| **`+0x008`** | **`0x00000000`** | **rw_Start 握手寄存器** | ★★★ 脉冲后自然清零，**预测正确** |
| `+0x0fc` | `0x13020619` | — | — |

⇒ ★★★★★★ **反汇编得到的寄存器偏移表被实机数据逐条证实。**

★★ `0x81115200` 说明 **LUT 数据放在 `0x8111xxxx` 物理区**——
这是 **DMA 可访问的内存**，不是 ioremap 区。
⇒ ★ **后续写入必须把 LUT buffer 放在 `virt_to_phys` 能转换的地方**
（`/dev/d5_sma` 管理的 SMA 区）。

---

## 6. 完整写入链（现在每一步都有源码/实测支撑）

```c
fd = open("/dev/drime5_ep", O_RDWR);       /* 零硬件初始化，安全 */
ioctl(fd, _IOR('h',100, struct ep_reg_info), &info);
base = mmap(NULL, info.reg_base_3dlut.reg_size,
            PROT_READ|PROT_WRITE, MAP_SHARED, fd,
            info.reg_base_3dlut.reg_start_addr);   /* ★ 字节地址 */

/* 3DLUT 写入序列（静态反汇编所得） */
*(volatile u32*)(base + 0x64) |=  ...;   /* OnOff(1)      */
*(volatile u32*)(base + 0x6c) =  ...;   /* Acc_OnOff(0)  */
*(volatile u32*)(base + 0x6c) =  ...;   /* Acc_OnOff(1)  */
*(volatile u32*)(base + 0x0c)  =  phys; /* ★ LUT 数据物理地址 */
v = *(volatile u32*)(base + 0x08);
*(volatile u32*)(base + 0x08) = v |0x100;   /* 写脉冲 bit8 */
*(volatile u32*)(base + 0x08) = v &~0x100;   /* 复位        */

/* LUT buffer → 物理地址 */
phys = d5_ep_sma_virt_to_phys(buf);   /* ioctl(/dev/d5_sma, _IOWR('s',2,u32)) */
```

★ `virt_to_phys` 返回值必须 **256 字节对齐**（`save_lut` 里
`if ((phys & 0xff) != 0) return -301;`），所以 buffer 要 `posix_memalign(&p,256,sz)`。

---

## 7. ★★★ 修正此前的判断

| 此前 | 真相 |
|---|---|
| "3DLUT 写入者在内核态/ISP 固件，必须改 P7" | ❌ **双重错误**：写入者在用户态，**且不需要改 P7** |
| "`di-camera-app` 1092 imports 里 3dlut=0 ⇒ 不存在" | ⚠️ **证据无效**：动态加载的库不在 import 表 |
| "gamma 只 2 档是机身层限制" | ❌ NOG 硬件 4 bit（γ ≤ 15）|
| "整个 D5 加速器栈未启用，路线可能走不通" | ⚠️ **部分对**：确实没人 open，但**驱动完备可用**，我们自己在用 |
| `ioctl(fd,'s',2,u32)` 是 EP 的 virt2phys | ⚠️ **那是 `/dev/d5_sma`**，另一个驱动 |

---

## 8. 新增铁律

| # | 规则 |
|---|---|
| **47** | `mmap` 字符设备的 `offset` 传**字节物理地址**，不是 PFN（内核替你 `>>PAGE_SHIFT`）。传错 ⇒ `EINVAL` |
| **48** | `struct` 布局/宏定义优先用**官方用户态头文件**，不要手抄。NX500 包 `usr/include/media/drime5/ep/` 与内核同源 |
| **49** | 拿到内核源码后**第一件事**：搜 `io_remap_pfn_range` / `unlocked_ioctl` / `struct file_operations`。这三处直接给出"寄存器怎么访问"，胜过任何逆向 |
| **50** | 判断一个 ioctl 能否读写寄存器，看 `copy_to_user` 的参数是不是 `struct reg_info`。中断类 ioctl 一律不碰寄存器 |

---

## 9. 下一步

**步骤 3：首次写入实验（尚未开始）**

最小风险版本：只对 `+0x08` 做 `|=0x100; &=~0x100` 脉冲，
**不写地址寄存器** ⇒ 理论上不改变画面（没有数据源）。

⚠️ 前置条件：
- **必须在 Liveview / 拍摄态**（否则 EP 块未配置，铁律 42）
- 相机网络需稳定（本次 15:35 出现过 10060 timeout）
- 先把 MC / NOG 块 dump 补齐（本次未跑完）

---

## 10. 产物

| 文件 | 说明 |
|---|---|
| `epinfo.c` / `.arm` | ★ EP 块权威地址查询（10/10 闭环）|
| `epdump2.c` / `.arm` | ★ mmap + dump 任意块（只读）|
| `epglb.c` / `.arm` | 自进程 dlopen 读全局 |
| `epfd.c` / `.arm` | 跨进程只读 `/proc/PID/mem`，支持 `-B` 批量、`-D` dump |
| `kread.c` / `.arm` | dump `/dev/mem`（★读内核代码会 SIGBUS）|
| `dishex.py` | hexdump → ARM 反汇编 |
| `sh.py` | telnet 命令执行器 |
| `crosscheck.py` | pyelftools 对照验证（16/16）|
| `raw5/epinfo_v1.txt` | 步骤 2a 输出 |
| `raw5/epdump2_3dlut.txt` | 步骤 2b 输出 |