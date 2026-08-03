# qcom-meta-tools

Qualcomm IPQ 平台镜像、分区表及单镜像打包工具。本分支已从 Python 2.7
移植到 Python 3.12。

## 运行环境

- Python 3.12（当前验证版本：Python 3.12.3）
- U-Boot `mkimage`（生成最终 FIT 镜像时需要）
- Device Tree Compiler `dtc`（涉及设备树处理时需要）

脚本只使用 Python 标准库，不需要安装额外的 Python 包。建议显式使用
`python3.12`；主入口通过 `sys.executable` 调用子脚本，可确保整个流程使用
同一个 Python 解释器。

查看入口参数：

```bash
python3.12 prepareSingleImage.py --help
```

## 使用示例

以 IPQ6018 NAND 分区表为例：

1. 按目标布局修改 `ipq6018/flash_partition/nand-partition.xml`。
2. 生成分区表：

   ```bash
   python3.12 prepareSingleImage.py --arch ipq6018 --fltype nand --genpart
   ```

3. 输出文件位于：

   ```text
   ipq6018/in/nand-system-partition-ipq6018.bin
   ```

如需指定输出目录，可使用 `--in <目录>`；其他架构、闪存类型及镜像生成参数
请参阅 `--help` 输出。

## Python 3.12 移植说明

- 将 Python 2 的 `print`、异常捕获和异常抛出语法更新为 Python 3 语法。
- 修正整数除法、字节写入、十六进制转换及 XML 迭代器等 Python 3 行为差异。
- 子脚本统一由当前 `sys.executable` 启动，避免环境中 `python` 命令指向错误版本。
- 命令行入口会将内部错误返回值传递为非零进程退出码，便于自动化流程可靠地
  检测生成失败。
- `pack.py` 以二进制模式解析 GPT/MIBIB，并显式解码 GPT UTF-16LE 名称与
  MIBIB ASCII 名称。
- Flash 几何计算保持整数语义；需要动态更新的分区参数写入临时 XML，生成过程
  不再覆盖仓库中的源配置。
- 为可执行入口补充 Python 3 shebang。
- 清理 `pack.py` 及相关脚本的 Tab/Space 混用，`pack.py` 现已统一使用空格缩进。
- 新增纯 Python `scripts/partition_tool.py`，生成流程不再依赖原有 32 位
  `partition_tool`/`nor_tool`；支持默认配置中的 NAND、NOR 和 NOR+NAND
  布局，包括 2048/4096 字节 NAND page。

## 测试与校验

以下检查已在 Python 3.12.3 环境通过：

```bash
# pack.py 语法及缩进校验，退出码为 0
python3.12 -m py_compile pack.py

# 全仓 Python 脚本严格编译，退出码为 0
git ls-files -co --exclude-standard -z -- '*.py' \
  | xargs -0 python3.12 -W error::SyntaxWarning -m py_compile

# 主入口帮助信息可正常输出，退出码为 0
python3.12 prepareSingleImage.py --help
```

此外，已使用仓库目录中的 Python 2.7 虚拟环境运行迁移前版本作为独立基准，
并使用 Python 3.12 运行迁移后版本。仓库默认配置生成的确定性产物已经完成
逐字节对照，结果完全一致；纯 Python 分区工具也已针对默认配置与原 32 位工具
逐字节校验通过。测试同时验证了真实 GPT/MIBIB 解析结果、失败退出码、生成文件名
与配置引用的一致性，以及生成前后源 XML 保持不变。

上述校验覆盖仓库默认配置可生成的产物范围，不代表对非法参数、未公开参数或
仓库未使用功能的兼容性承诺。实际生成完整镜像时仍需准备对应平台的输入二进制
文件，并按所用功能安装 `mkimage`、`dtc` 等主机工具。
