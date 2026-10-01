"""课程内容 v2 的唯一结构定义。

Pydantic 判别联合 → JSON Schema（curriculum/schema/content.v2.schema.json）→ 前端 TS 类型。
块类型与场景无关；场景顺序固定为 理解 / 读码 / 实验 / 自检 / 回顾。
每个块与条目都有稳定 id，译文层按 id 合并；带 x-fact 标记的字段是事实，译文不得覆盖。
校验与补默认值分开：默认值只在这里声明一次。
"""
from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

CONTENT_VERSION = 2

Id = Annotated[str, Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=64,
                          json_schema_extra={"x-fact": True})]
Text = Annotated[str, Field(min_length=1)]
Fact = Annotated[str, Field(min_length=1, json_schema_extra={"x-fact": True})]
Url = Annotated[str, Field(pattern=r"^https?://\S+$", json_schema_extra={"x-fact": True})]

# 表现形式只写语义意图，由前端动效层映射到具体组件（见 frontend/src/motion/intents.tsx）。
Reveal = Literal["none", "fade", "split", "decode", "blur"]
Capability = Literal["model", "tools", "knowledge", "context", "memory", "planning",
                     "orchestration", "trust"]


class Strict(BaseModel):
    # 输出形态的 schema 把有默认值的字段标为必有：接口返回总是补齐默认值。
    model_config = ConfigDict(extra="forbid", json_schema_serialization_defaults_required=True)


def _unique(ids: list[str], what: str) -> None:
    seen: set[str] = set()
    for identifier in ids:
        if identifier in seen:
            raise ValueError(f"{what} id 重复：{identifier}")
        seen.add(identifier)


class Item(Strict):
    id: Id
    text: Text


class Block(Strict):
    id: Id


# ---------- 通用块 ----------

class Hero(Block):
    type: Literal["hero"]
    eyebrow: Text
    headline: Text
    highlight: Text | None = None
    takeaway: Text | None = None
    reveal: Reveal = "split"


class Prose(Block):
    type: Literal["prose"]
    title: Text | None = None
    paragraphs: list[Text] = Field(min_length=1)
    reveal: Reveal = "none"


class Concept(Strict):
    id: Id
    label: Text
    title: Text
    description: Text
    token: Fact | None = None


class Concepts(Block):
    type: Literal["concepts"]
    title: Text | None = None
    items: list[Concept] = Field(min_length=1)
    layout: Literal["grid", "flip", "stack"] = "grid"

    @model_validator(mode="after")
    def _ids(self):
        _unique([item.id for item in self.items], "concepts.items")
        return self


class Steps(Block):
    type: Literal["steps"]
    title: Text | None = None
    paragraphs: list[Text] = []
    items: list[Item] = Field(min_length=1)

    @model_validator(mode="after")
    def _ids(self):
        _unique([item.id for item in self.items], "steps.items")
        return self


class Compare(Block):
    type: Literal["compare"]
    title: Text | None = None
    paragraphs: list[Text] = []
    columns: list[Text] = Field(min_length=2)
    rows: list[list[Text]] = Field(min_length=1)

    @model_validator(mode="after")
    def _shape(self):
        for index, row in enumerate(self.rows):
            if len(row) != len(self.columns):
                raise ValueError(f"compare.rows[{index}] 的列数必须与 columns 相同")
        return self


class Callout(Block):
    type: Literal["callout"]
    tone: Literal["note", "warning", "boundary"] = "note"
    title: Text | None = None
    paragraphs: list[Text] = Field(min_length=1)


class Misconception(Block):
    type: Literal["misconception"]
    claim: Text
    correction: Text


class Objectives(Block):
    type: Literal["objectives"]
    items: list[Item] = Field(min_length=1)


class Reference(Strict):
    id: Id
    title: Text
    url: Url


class References(Block):
    type: Literal["references"]
    items: list[Reference] = Field(min_length=1)


class WalkStep(Strict):
    id: Id
    label: Text
    actor: Text
    title: Text
    body: Text
    code: Fact | None = None
    language: Fact = "text"
    evidence: Text | None = None


class Walkthrough(Block):
    """作者写的分步讲解，属于教学示意：界面必须标注“教学示意 · 非运行记录”。"""
    type: Literal["walkthrough"]
    provenance: Literal["illustration"] = "illustration"
    title: Text
    description: Text | None = None
    steps: list[WalkStep] = Field(min_length=1)

    @model_validator(mode="after")
    def _ids(self):
        _unique([step.id for step in self.steps], "walkthrough.steps")
        return self


class Flow(Block):
    """用 illustrations 中的合成事件序列驱动舞台（同一个 deriveStage 渲染）。"""
    type: Literal["flow"]
    title: Text | None = None
    illustration: Id
    caption: Text | None = None


# ---------- 自测与预测 ----------

class QuizOption(Strict):
    id: Id
    text: Text
    feedback: Text | None = None  # 选项级反馈：为什么这个选项对或错


class QuizQuestion(Strict):
    id: Id
    prompt: Text
    options: list[QuizOption] = Field(min_length=2)
    correct: Id
    explanation: Text

    @model_validator(mode="after")
    def _answer(self):
        _unique([option.id for option in self.options], "quiz.options")
        if self.correct not in {option.id for option in self.options}:
            raise ValueError(f"quiz {self.id} 的 correct 必须引用已有选项")
        return self


class MicroQuiz(Block):
    type: Literal["micro-quiz"]
    question: QuizQuestion


class Quiz(Block):
    type: Literal["quiz"]
    title: Text | None = None
    confidence: bool = True  # 先评信心再作答
    questions: list[QuizQuestion] = Field(min_length=1)

    @model_validator(mode="after")
    def _ids(self):
        _unique([question.id for question in self.questions], "quiz.questions")
        return self


class CountEvents(Strict):
    """只比较能从真实事件推出的事实：统计某类事件（可按工具名过滤）。"""
    kind: Literal["count_events"]
    event: Fact
    name: Fact | None = None


class Predict(Block):
    type: Literal["predict"]
    prompt: Text
    experiment: Id
    rule: CountEvents


class Checkpoint(Block):
    """学习者自报的检查点；平台只记录勾选，不判定掌握。"""
    type: Literal["checkpoint"]
    title: Text
    prompt: Text | None = None
    items: list[Item] = Field(min_length=1)

    @model_validator(mode="after")
    def _ids(self):
        _unique([item.id for item in self.items], "checkpoint.items")
        return self


class Selector(Strict):
    """观察点、导览和轨迹找错共用的声明式选择器；至少给出一个条件。"""
    event: Fact | None = None
    round: Annotated[int, Field(ge=1)] | None = None
    path: Fact | None = None       # JSON 路径，如 data.tool_calls[0].function.name
    span_kind: Fact | None = None
    name: Fact | None = None       # 工具名

    @model_validator(mode="after")
    def _not_empty(self):
        if not self.model_dump(exclude_none=True):
            raise ValueError("selector 至少需要一个条件")
        return self


class TraceHunt(Block):
    type: Literal["trace-hunt"]
    prompt: Text
    target: Selector
    explanation: Text


# ---------- 读码 ----------

class WhatsNew(Block):
    """本课新增内容由后端从真实源码计算，这里只声明对比基准。"""
    type: Literal["whats-new"]
    compare_with: Id | None = None


class SourceNote(Strict):
    id: Id
    line: Annotated[int, Field(ge=1)]
    text: Text


class AnnotatedSource(Block):
    type: Literal["annotated-source"]
    path: Fact
    start: Annotated[int, Field(ge=1)] | None = None
    end: Annotated[int, Field(ge=1)] | None = None
    notes: list[SourceNote] = []

    @model_validator(mode="after")
    def _range(self):
        if self.start and self.end and self.end < self.start:
            raise ValueError("annotated-source 的 end 不能小于 start")
        _unique([note.id for note in self.notes], "annotated-source.notes")
        return self


class Alternative(Strict):
    id: Id
    title: Text
    why_not: Text


class Decision(Block):
    type: Literal["decision"]
    title: Text
    chosen: Text
    alternatives: list[Alternative] = []


AnyBlock = Annotated[
    Union[Hero, Prose, Concepts, Steps, Compare, Callout, Misconception, Objectives,
          References, Walkthrough, Flow, MicroQuiz, Quiz, Predict, Checkpoint, TraceHunt,
          WhatsNew, AnnotatedSource, Decision],
    Field(discriminator="type"),
]


# ---------- 实验 ----------

class ObservePoint(Strict):
    id: Id
    text: Text
    selector: Selector | None = None  # 迁移来的旧提示暂无选择器


class Narrate(Strict):
    action: Literal["narrate"]
    text: Text


class Spotlight(Strict):
    action: Literal["spotlight"]
    target: Fact  # 舞台节点角色，如 model / runtime / tool / memory


class Highlight(Strict):
    action: Literal["highlight"]
    observe: Id


class Seek(Strict):
    action: Literal["seek"]
    observe: Id


GuideAction = Annotated[Union[Narrate, Spotlight, Highlight, Seek],
                        Field(discriminator="action")]


class Arm(Strict):
    id: Id
    exercise: Fact  # lesson.json 中的练习 id
    label: Text | None = None
    inputs: dict[str, Any] | None = Field(default=None, json_schema_extra={"x-fact": True})


class Conclusion(Strict):
    proves: list[Text] = []
    does_not_prove: list[Text] = []


class Experiment(Strict):
    id: Id
    title: Text
    hypothesis: Text | None = None
    predict: Id | None = None
    arms: list[Arm] = Field(min_length=1)
    observe: list[ObservePoint] = []
    guide: list[GuideAction] = []
    conclusion: Conclusion | None = None

    @model_validator(mode="after")
    def _refs(self):
        _unique([arm.id for arm in self.arms], "experiment.arms")
        _unique([point.id for point in self.observe], "experiment.observe")
        observe_ids = {point.id for point in self.observe}
        for action in self.guide:
            if isinstance(action, (Highlight, Seek)) and action.observe not in observe_ids:
                raise ValueError(f"实验 {self.id} 的导览引用了不存在的观察点 {action.observe}")
        return self


# ---------- 场景与文档 ----------

class BlockScene(Strict):
    blocks: list[AnyBlock] = Field(min_length=1)


class InputOption(Strict):
    value: Fact
    label: Text


class InputField(Strict):
    """为 INPUT_MODEL 的字段提供可翻译的标签；控件类型由后端导出的 JSON Schema 决定。"""
    name: Fact  # INPUT_MODEL 字段名
    label: Text
    help: Text | None = None
    options: list[InputOption] = []

    @model_validator(mode="after")
    def _options(self):
        values = [option.value for option in self.options]
        if len(values) != len(set(values)):
            raise ValueError(f"输入 {self.name} 的选项值重复")
        return self


class LabScene(Strict):
    experiments: list[Experiment] = Field(min_length=1)
    inputs: list[InputField] = []
    blocks: list[AnyBlock] = []

    @model_validator(mode="after")
    def _inputs(self):
        names = [field.name for field in self.inputs]
        if len(names) != len(set(names)):
            raise ValueError("lab.inputs 的字段名重复")
        return self


class Scenes(Strict):
    understand: BlockScene | None = None
    code: BlockScene | None = None
    lab: LabScene | None = None
    check: BlockScene | None = None


class IllustrationEvent(Strict):
    type: Fact
    round: Annotated[int, Field(ge=1)] | None = None
    data: dict[str, Any] = Field(default_factory=dict, json_schema_extra={"x-fact": True})


class Illustration(Strict):
    provenance: Literal["illustration"] = "illustration"
    events: list[IllustrationEvent] = Field(min_length=1)

    @model_validator(mode="after")
    def _contract(self):
        from server.illustrations import validate_illustration  # 契约规则见该模块
        validate_illustration([event.model_dump() for event in self.events])
        return self


def _block_ids(blocks: list[Any]) -> list[str]:
    return [block.id for block in blocks]


def _validate_document(scenes: Scenes, illustrations: dict[str, Illustration]) -> None:
    blocks = [block for scene in (scenes.understand, scenes.code, scenes.check, scenes.lab)
              if scene for block in scene.blocks]
    experiments = scenes.lab.experiments if scenes.lab else []
    _unique(_block_ids(blocks) + [experiment.id for experiment in experiments], "块与实验")
    experiment_ids = {experiment.id for experiment in experiments}
    predict_ids = set()
    for block in blocks:
        if isinstance(block, Flow) and block.illustration not in illustrations:
            raise ValueError(f"flow {block.id} 引用了不存在的示意 {block.illustration}")
        if isinstance(block, Predict):
            predict_ids.add(block.id)
            if block.experiment not in experiment_ids:
                raise ValueError(f"predict {block.id} 引用了不存在的实验 {block.experiment}")
    for experiment in experiments:
        if experiment.predict and experiment.predict not in predict_ids:
            raise ValueError(f"实验 {experiment.id} 引用了不存在的预测块 {experiment.predict}")


# 只在文件里出现（编辑器补全），不进入接口输出。
SchemaRef = Annotated[str | None, Field(default=None, alias="$schema", exclude=True,
                                       json_schema_extra={"x-fact": True})]


class LessonContent(Strict):
    model_config = ConfigDict(extra="forbid", populate_by_name=True,
                              json_schema_serialization_defaults_required=True)

    schema_ref: SchemaRef = None  # 编辑器补全用的 $schema 相对路径
    schema_version: Literal[2]
    lesson: Id
    source_language: Fact  # 内容自己的源语言，与界面语言无关
    capabilities: list[Capability] = []
    scenes: Scenes
    illustrations: dict[str, Illustration] = {}

    @model_validator(mode="after")
    def _document(self):
        _validate_document(self.scenes, self.illustrations)
        return self


class Chapter(Strict):
    """导学章节：只启用 理解 与 自检。"""
    id: Id
    title: Text
    eyebrow: Text
    summary: Text
    estimated_minutes: Annotated[int, Field(ge=1, le=120)]
    next_label: Text | None = None
    scenes: Scenes
    illustrations: dict[str, Illustration] = {}

    @model_validator(mode="after")
    def _document(self):
        if self.scenes.code or self.scenes.lab:
            raise ValueError(f"导学章节 {self.id} 只能包含 understand 与 check")
        _validate_document(self.scenes, self.illustrations)
        return self


class Onboarding(Strict):
    model_config = ConfigDict(extra="forbid", populate_by_name=True,
                              json_schema_serialization_defaults_required=True)

    schema_ref: SchemaRef = None
    schema_version: Literal[2]
    source_language: Fact
    title: Text
    description: Text
    chapters: list[Chapter] = Field(min_length=1)

    @model_validator(mode="after")
    def _ids(self):
        _unique([chapter.id for chapter in self.chapters], "chapters")
        return self


def json_schemas() -> dict[str, dict[str, Any]]:
    """导出 JSON Schema：*.schema.json 是文件格式（编辑器补全）；
    *.output.schema.json 是补齐默认值后的接口输出形态，用来生成前端 TS 类型。"""
    return {
        "content.v2.schema.json": LessonContent.model_json_schema(),
        "onboarding.v2.schema.json": Onboarding.model_json_schema(),
        "content.v2.output.schema.json": LessonContent.model_json_schema(mode="serialization"),
        "onboarding.v2.output.schema.json": Onboarding.model_json_schema(mode="serialization"),
    }
