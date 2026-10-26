# Agent Dev Workflow

面向 Agent 软件开发的中文通用 skill，覆盖资源检查、计划、模块化并行、实现与验证、文件和文档维护、交付及知识沉淀。完整规则从 [SKILL.md](agent-dev-workflow/SKILL.md) 进入，各项细则按需读取。

个人小任务可复用“现有计划一段＋相关检查＋一条结果记录”；共同开发补充任务认领、共享资源协调及审查、合并、发布职责。采用 Git 时默认使用 `main` / `test`，验证后通过 PR 或平台允许的直接合入更新 `main`；特殊需要可创建按用途命名的分支。

具备独立实施条件的工作包默认交多个 subagent 同批并行，主 agent 统一接口、集成和交付；确无独立工作或环境受限时，说明原因并调整调度。三项核心原则是：**目标优先、复杂度相称；真实行为优先；后果与证据匹配。** 纯问答、只读审查和仅整理操作经验按各自边界处理。

## 安装与调用

1. 克隆本仓库：

   ```sh
   git clone https://github.com/Panda-Panta/agent-dev-workflow.git
   ```

2. 找到所用 Agent 环境实际读取的 skills 目录，将仓库内的 **`agent-dev-workflow/` 子目录完整复制**过去，保持 `SKILL.md`、`agents/`、`assets/`、`references/` 和 `scripts/` 的相对位置。目标已存在时，先比较差异并备份，保留自己的修改，再同步需要更新的文件。
3. 在该环境中确认技能可被发现；需要重新加载时按宿主环境的方式操作。随后可显式调用：

   ```text
   使用 $agent-dev-workflow 完成当前开发任务，沿用项目已有计划和授权。
   ```

4. 需要作为项目默认约定时，将 [AGENTS 入口片段](agent-dev-workflow/assets/AGENTS.project-snippet.md) 合并进项目现有 `AGENTS.md`，填写实际技能、计划、结构和文档入口，保留项目其他规则。

技能包含允许隐式调用的元数据，实际发现、自动调用和 subagent 能力取决于宿主环境。复制文件或通过格式校验不能证明新会话已加载；请在所用环境确认调用结果。目录索引工具另需 Python 3，可先查看其 `--help`；使用已有等价工具的项目可继续沿用。

## 按任务查阅

| 需要处理的内容 | 入口 |
| --- | --- |
| 完整流程、决策与证据原则 | [主 skill](agent-dev-workflow/SKILL.md) |
| 个人与共同开发、验证和审查 | [开发模式](agent-dev-workflow/references/development-modes.md) |
| 计划、源码结构与模板选择 | [规划与维护](agent-dev-workflow/references/planning.md) |
| 并行派工、文件归属与集成 | [并行规则](agent-dev-workflow/references/parallel.md) |
| 工具、文档、产物分类及清理 | [文件与自动化](agent-dev-workflow/references/files-and-automation.md) |
| 开发日志、使用说明与交接 | [文档规范](agent-dev-workflow/references/documentation.md) |
| 分支、远端、安装与回退 | [交付规则](agent-dev-workflow/references/delivery.md) |
| 已完成流程的文档与领域 skill 沉淀 | [知识沉淀](agent-dev-workflow/references/domain-skills.md) |
| 本仓库维护方式与文件结构 | [项目计划](DEVELOPMENT_PLAN.md) |

本仓库发布的是流程正文、模板及目录索引工具；实际任务仍须按目标验证，并分别记录源码、制品、安装文件和运行结果。规则不会自动授予推送、公开发布、停机或删除用户数据的权限。

## 来源与许可

协作与执行部分融合了 [wwwort/human-first-agent-skills](https://github.com/wwwort/human-first-agent-skills) 的 `human-first-execution`，固定来源提交为 [`54e284fcd7d6a565fc2c229e50dbf20d535f5cd2`](https://github.com/wwwort/human-first-agent-skills/tree/54e284fcd7d6a565fc2c229e50dbf20d535f5cd2)。融合范围与取舍见 [来源说明](agent-dev-workflow/references/human-first.md)。

已保留原作者 wwwort 的 [MIT 版权与许可全文](agent-dev-workflow/references/human-first-agent-skills.LICENSE.txt)；该许可适用于引用、改编的上游材料，不据此为其他内容追加许可。
