from __future__ import annotations
import random
import inspect
from enum import Enum
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Callable, Any, Iterator, List, Union
from heapq import nsmallest
import math
import time
from multiprocessing import Pool, cpu_count
from collections import Counter

class COWList:
  __slots__ = ("_data", "_shared")
  def __init__(self, data : list, shared=False):
    self._data = data
    self._shared = shared
  def fork(self):
    return COWList(self._data, shared=True)
  def _ensure_own(self):
    if self._shared:
      self._data = self._data.copy()
      self._shared = False
  def __getitem__(self, i):
    return self._data[i]
  def __len__(self):
    return len(self._data)
  def __setitem__(self, i, value):
    self._ensure_own()
    self._data[i] = value
  def append(self, value):
    self._ensure_own()
    self._data.append(value)
  def __str__(self):
    return f"{self._data}"
  def __repr__(self):
    return self.__str__()

class BattleRange(Enum):
  LOSS = 0
  DISADVANTAGE = 1
  DRAW = 2
  ADVANTAGE = 3
  WIN = 4
  BEGIN = 5
  def __str__(self):
    if self.value == 0:
      return "失败"
    elif self.value == 1:
      return "下风"
    elif self.value == 2:
      return "均势"
    elif self.value == 3:
      return "上风"
    elif self.value == 4:
      return "胜利"
    else:
      return "开局"
    # return f"{self.name}"
  def __repr__(self):
    return self.__str__()
  def __add__(self, x : int):
    v = self.value + x
    if v <= 0: v = 0
    elif v >= 4: v = 4
    return BattleRange(value=v)
  def __sub__(self, x : int):
    return self.__add__(-x)
  def __lt__(self, other : BattleRange):
    return self.value < other.value
  def __gt__(self, other : BattleRange):
    return self.value > other.value
  def __le__(self, other : BattleRange):
    return self.value <= other.value
  def __ge__(self, other : BattleRange):
    return self.value >= other.value

class SkillType(Enum):
  ST_ROLL_DICE = 1
  ST_ADD = 2
  ST_ETERNAL_MODIFY_STATE = 3
  ST_GET_NUM = 4
  ST_EXTRA_ATK = 5
  ST_MODIFY_NUM = 6
  ST_MODIFY_STATE = 7
  ST_GROUP = 8
  ST_CHECKER = 9
  ST_DELIVER = 10
  ST_CHAIZHAO = 11

# different dice
class base_dice:
  def __init__(self):
    pass
  def __call__(self):
    return random.randint(1, 10)
  def __init_subclass__(cls):
    super().__init_subclass__()
    # 获取 __call__ 签名
    base_sig = inspect.signature(base_dice.__call__)
    sub_sig = inspect.signature(cls.__call__)
    # 比较签名：可换成更严的校验策略
    if sub_sig != base_sig:
      raise TypeError(
        f"{cls.__name__}.__call__ 的签名 {sub_sig} 不匹配基类签名 {base_sig}"
      )
  def __repr__(self):
    return self.__str__()
  def __str__(self):
    return "在 1-10 间均匀随机"
  def clear(self):
    pass  # some dice may need to clear some tmp variables here
class dice_crash(base_dice):
  def __init__(self, p_crash: float):
    self.p_crash = p_crash
    self.last_die = 0
  def __call__(self):
    if self.last_die == 0:
      self.last_die = base_dice()()
      return self.last_die
    else:
      if random.random() <= self.p_crash:
        if self.last_die == 10:
          self.last_die = 1
          return self.last_die
        else:
          self.last_die += 1
          return self.last_die
      else:
        self.last_die = base_dice()()
        return self.last_die
  def __str__(self):
    return f"有 {self.p_crash} 概率撞车的骰子"
  def clear(self):
    self.last_die = 0
class dice_crash_and_control(base_dice):
  def __init__(self, p_crash: float, p_control: float, control_distribute: dict):
    self.last_die = 0
    self.p_crash = p_crash
    self.p_control = p_control
    self.control_distribute = control_distribute
  def __call__(self):
    if self.last_die == 0:
      self.last_die = base_dice()()
    else:
      mode = random.random()
      if mode <= self.p_crash:
        if self.last_die == 10:
          self.last_die = 1
        else:
          self.last_die += 1
      elif self.p_crash < mode <= self.p_crash + self.p_control:
        control_mode = random.random()
        for key, value in self.control_distribute.items():
          control_mode -= value
          if control_mode > 0:
            continue
          if key > self.last_die:
            self.last_die = key - self.last_die
          else:
            self.last_die = 10 + key - self.last_die
          break
    return self.last_die
  def __str__(self):
    return f"有 {self.p_crash} 概率撞车，{self.p_control} 概率控骰，控骰结果分布为 {self.control_distribute}"
  def clear(self):
    self.last_die = 0

LOSS, DISADVANTAGE, DRAW, ADVANTAGE, WIN, BEGIN = BattleRange
ST_ROLL_DICE, ST_ADD, ST_ETERNAL_MODIFY_STATE, ST_GET_NUM, ST_EXTRA_ATK, ST_MODIFY_NUM, ST_MODIFY_STATE, ST_GROUP, ST_CHECKER, ST_DELIVER, ST_CHAIZHAO = SkillType
GREATER, LESS = True, False
COMMON_RANGE = [LOSS, DISADVANTAGE, DISADVANTAGE, DISADVANTAGE, DRAW, DRAW, ADVANTAGE, ADVANTAGE, ADVANTAGE, WIN]
# COMMON_RANGE_REV = [LOSS, ADVANTAGE, ADVANTAGE, ADVANTAGE, DRAW, DRAW, DISADVANTAGE, DISADVANTAGE, DISADVANTAGE, WIN]

def turn_one_range(lst: list, state_from: SkillType, state_to: SkillType):
  choice = None
  for i, state in enumerate(lst):
    if state == state_from:
      choice = i
  if choice is not None:
    lst[choice] = state_to
def range_uplevel(b: BattleRange):
  if b == BattleRange.LOSS:
    return BattleRange.DISADVANTAGE
  elif b == BattleRange.DISADVANTAGE:
    return BattleRange.DRAW
  elif b == BattleRange.DRAW:
    return BattleRange.ADVANTAGE
  elif b == BattleRange.ADVANTAGE:
    return BattleRange.WIN
  else:
    return BattleRange.WIN
def range_declevel(b: BattleRange):
  if b == BattleRange.LOSS:
    return BattleRange.LOSS
  elif b == BattleRange.DISADVANTAGE:
    return BattleRange.LOSS
  elif b == BattleRange.DRAW:
    return BattleRange.DISADVANTAGE
  elif b == BattleRange.ADVANTAGE:
    return BattleRange.DRAW
  else:
    return BattleRange.ADVANTAGE
def get_range_level(lst: list, num: int):
  if num < 1:
    return BattleRange.LOSS
  elif num > 10:
    return BattleRange.WIN
  else:
    return lst[num - 1]
def range_reverse(b: BattleRange):
  if b == BattleRange.WIN:
    return BattleRange.LOSS
  elif b == BattleRange.ADVANTAGE:
    return BattleRange.DISADVANTAGE
  elif b == BattleRange.DISADVANTAGE:
    return BattleRange.ADVANTAGE
  elif b == BattleRange.LOSS:
    return BattleRange.WIN
  else:
    return b
def range_level_change(b: BattleRange, num: int):
  state = b
  while num > 0:
    state = range_uplevel(state)
    num -= 1
  while num < 0:
    state = range_declevel(state)
    num += 1
  return state
def num_reverse(num: int):
  return 11 - num
def two_tail_sum(lst: list):
  if len(lst) == 0:
    return random.randint(1, 10)
  elif len(lst) == 1:
    return lst[0]
  else:
    x = lst[0] + lst[1]
    if x > 10:
      return x - 10
    else:
      return x

# player
class player:
  def __init__(self, skills: list, num: int = 0):
    self.skills = skills
    self.name = ""
    self.hp = 6 # calc the hurt
    self.num = num
  def __str__(self):
    return f"{self.skills}, 招式等级：{self.num}"
# game
class game:
  def __init__(self, greater_player: player, less_player: player, dice: base_dice, mode_method: dict):
    self.state_lst = COWList(data=COMMON_RANGE, shared=False)  # long lasting effect
    self.tmp_state_lst = self.state_lst.fork()  # just tmp
    self.greater_player = deepcopy(greater_player)
    self.less_player = deepcopy(less_player)
    self.dice_history = []
    self.dice_result_history = []
    self.state_history = [BEGIN] # 新加入一个哨兵节点
    self.add = 0
    self.situation_add = 0
    self.turn = 0  # number of the turn
    self.dice = dice  # how to get the dice
    self.last_value = 0  # final value of last turn
    self.last_state = BEGIN
    self.value_history = []
    self.chaizhao_history = []
    self.mode_method = mode_method
    self.is_state_locked = False
    self.chaizhao_add = 0
    self.skill_type_now = ST_ADD # for a pause
    self.dice_this_turn = None # 当前回合骰子的值
    self.game_counter = Counter()
    # 永久加值 pool
    self.eternal_skill_plus = {}
    self._eternal_effect_id = 0
    self.last_eternal_skill_plus = 0 # 维护一个 last eternal skill plus，避免外部访问时重复 eval
    self.init_skills()
  def add_eternal_effect(self, skill_name, expr, is_greater, info=None):
    side = "G" if is_greater else "L"
    key = f"{skill_name}:{side}:{self._eternal_effect_id}"
    self._eternal_effect_id += 1
    self.eternal_skill_plus[key] = {
      "expr": expr,
      "is_greater": is_greater,
      "info": info,
    }
  def eval_eternal_skill_plus(self, is_chaizhao=False):
    total = 0
    for key, effect in list(self.eternal_skill_plus.items()):
      expr = effect["expr"]
      is_greater = effect["is_greater"]
      info = effect["info"]
      if isinstance(expr, Expr):
        val = expr.eval(self, is_greater, is_chaizhao, info)
      else:
        val = expr
      if val is None: continue
      if not isinstance(val, int):
        raise TypeError(f"eternal effect {key} returns non-int value: {val}")
      total += val if is_greater else -val
    return total
  def init_skills(self):
    self.skill_type_now = None
    for skill in self.greater_player.skills:
      for s in self.iter_skills(skill):
        if isinstance(s, r_skill):
          s.init_skill(self, GREATER)
    for skill in self.less_player.skills:
      for s in self.iter_skills(skill):
        if isinstance(s, r_skill):
          s.init_skill(self, LESS)
  def get_chaizhao_add(self):
    self.chaizhao_add = self.greater_player.num - self.less_player.num
    self.skill_type_now = ST_CHAIZHAO
    for skill in self.greater_player.skills:
      if skill.type == ST_CHAIZHAO:
        skill(self, GREATER, True)
      elif skill.type == ST_GROUP:
        self.imply_group_skill(GREATER, True, skill, ST_CHAIZHAO)
    for skill in self.less_player.skills:
      if skill.type == ST_CHAIZHAO:
        skill(self, LESS, True)
      elif skill.type == ST_GROUP:
        self.imply_group_skill(LESS, True, skill, ST_CHAIZHAO)
    return self.chaizhao_add
  def imply_group_skill(self, is_greater: bool, is_chaizhao: bool, skill, skill_type: SkillType):
    for subskill in skill.sub_skills:
      if subskill.type == skill_type:
        subskill(self, is_greater, is_chaizhao)
  def get_dice_result(self, is_chaizhao: bool):
    dice_history = []
    dice_history.append(self.dice())
    dice_history.append(self.dice())
    self.dice_history.append(dice_history)
    self.skill_type_now = ST_ROLL_DICE
    for skill in self.greater_player.skills:
      if skill.type == ST_ROLL_DICE:
        skill(self, GREATER, is_chaizhao)
      elif skill.type == ST_GROUP:
        self.imply_group_skill(GREATER, is_chaizhao, skill, ST_ROLL_DICE)
    for skill in self.less_player.skills:
      if skill.type == ST_ROLL_DICE:
        skill(self, LESS, is_chaizhao)
      elif skill.type == ST_GROUP:
        self.imply_group_skill(LESS, is_chaizhao, skill, ST_ROLL_DICE)
    self.skill_type_now = ST_GET_NUM
    for skill in self.greater_player.skills:
      if skill.type == ST_GET_NUM:
        x = skill(self, GREATER, is_chaizhao)
        if x is not None:
          return x
      elif skill.type == ST_GROUP:
        for subskill in skill.sub_skills:
          if subskill.type == ST_GET_NUM:
            x = subskill(self, GREATER, is_chaizhao)
            if x is not None:
              return x
    for skill in self.less_player.skills:
      if skill.type == ST_GET_NUM:
        x = skill(self, LESS, is_chaizhao)
        if x is not None:
          return x
      elif skill.type == ST_GROUP:
        for subskill in skill.sub_skills:
          if subskill.type == ST_GET_NUM:
            x = subskill(self, LESS, is_chaizhao)
            if x is not None:
              return x
    return two_tail_sum(dice_history)
  def get_add_value(self, is_chaizhao: bool):
    self.add = 0
    self.skill_type_now = ST_ADD
    for skill in self.greater_player.skills:
      if skill.type == ST_ADD:
        skill(self, GREATER, is_chaizhao)
      elif skill.type == ST_GROUP:
        self.imply_group_skill(GREATER, is_chaizhao, skill, ST_ADD)
    for skill in self.less_player.skills:
      if skill.type == ST_ADD:
        skill(self, LESS, is_chaizhao)
      elif skill.type == ST_GROUP:
        self.imply_group_skill(LESS, is_chaizhao, skill, ST_ADD)
  def get_value(self, is_chaizhao: bool):
    dice = self.get_dice_result(is_chaizhao)
    self.dice_this_turn = dice
    if not is_chaizhao:
      self.dice_result_history.append(dice)
    self.get_add_value(is_chaizhao)
    self.last_value = dice + self.add
    if not is_chaizhao:
      self.last_value += self.situation_add
      # 局面加值
      self.last_eternal_skill_plus = self.eval_eternal_skill_plus(False)
      self.last_value += self.last_eternal_skill_plus
      # 技能的永久加值
    else:
      self.last_value += self.get_chaizhao_add()
    self.skill_type_now = ST_MODIFY_NUM
    for skill in self.greater_player.skills:
      if skill.type == ST_MODIFY_NUM:
        skill(self, GREATER, is_chaizhao)
      elif skill.type == ST_GROUP:
        self.imply_group_skill(GREATER, is_chaizhao, skill, ST_MODIFY_NUM)
    for skill in self.less_player.skills:
      if skill.type == ST_MODIFY_NUM:
        skill(self, LESS, is_chaizhao)
      elif skill.type == ST_GROUP:
        self.imply_group_skill(LESS, is_chaizhao, skill, ST_MODIFY_NUM)
    self.value_history.append(self.last_value)
  def get_state(self, calc_value : bool = True):
    self.is_state_locked = False
    if calc_value: self.get_value(False)
    self.skill_type_now = ST_ETERNAL_MODIFY_STATE
    for skill in self.greater_player.skills:
      if skill.type == ST_ETERNAL_MODIFY_STATE:
        skill(self, GREATER, False)
      elif skill.type == ST_GROUP:
        self.imply_group_skill(GREATER, False, skill, ST_ETERNAL_MODIFY_STATE)
    for skill in self.less_player.skills:
      if skill.type == ST_ETERNAL_MODIFY_STATE:
        skill(self, LESS, False)
      elif skill.type == ST_GROUP:
        self.imply_group_skill(LESS, False, skill, ST_ETERNAL_MODIFY_STATE)
    # self.tmp_state_lst = deepcopy(self.state_lst)
    self.tmp_state_lst = self.state_lst.fork()
    self.skill_type_now = ST_MODIFY_STATE
    for skill in self.greater_player.skills:
      if skill.type == ST_MODIFY_STATE:
        skill(self, GREATER, False)
      elif skill.type == ST_GROUP:
        self.imply_group_skill(GREATER, False, skill, ST_MODIFY_STATE)
    for skill in self.less_player.skills:
      if skill.type == ST_MODIFY_STATE:
        skill(self, LESS, False)
      elif skill.type == ST_GROUP:
        self.imply_group_skill(LESS, False, skill, ST_MODIFY_STATE)
    if not self.is_state_locked:
      self.last_state = get_range_level(self.tmp_state_lst, self.last_value)
  def simulate_one_turn(self):
    self.dice.clear()
    self.get_state()
    self.turn += 1  # time pass by
    # print(f"拆招之前 {self.last_state}")
    self.extra_calc()
    self.state_history.append(self.last_state)
    if self.last_state == WIN:
      return (WIN, self.turn)
    elif self.last_state == ADVANTAGE:
      self.situation_add += 1
    elif self.last_state == DRAW:
      pass
    elif self.last_state == DISADVANTAGE:
      self.situation_add -= 1
    elif self.last_state == LOSS:
      return (LOSS, self.turn)
    return (self.last_state, self.turn)
  def extra_calc(self):  # for continue advantages and hurt
    self.skill_type_now = ST_EXTRA_ATK
    for skill in self.greater_player.skills:
      if skill.type == ST_EXTRA_ATK:
        skill(self, GREATER, False)
      elif skill.type == ST_GROUP:
        self.imply_group_skill(GREATER, False, skill, ST_EXTRA_ATK)
    for skill in self.less_player.skills:
      if skill.type == ST_EXTRA_ATK:
        skill(self, LESS, False)
      elif skill.type == ST_GROUP:
        self.imply_group_skill(LESS, False, skill, ST_EXTRA_ATK)
    # continue advatanges
    if len(self.state_history) >= 2:
      # 拆招规则
      if self.state_history[-1] == ADVANTAGE and self.state_history[-2] == ADVANTAGE:
        self.dice_result_history.append("连续优势拆招")
        self.chaizhao(mode = self.mode_method.get("advantage"))
      if self.state_history[-1] == DISADVANTAGE and self.state_history[-2] == DISADVANTAGE:
        self.dice_result_history.append("连续劣势拆招")
        self.chaizhao(mode = self.mode_method.get("disadvantage"))
  def chaizhao(self, greater_win = None, less_win = None, difficulty: int = 5, mode: str = "none"):  # two functions are needed
    self.get_value(True)  # Really, it is.
    if self.last_value > difficulty:
      self.chaizhao_history.append("通过")
      if greater_win is None:
        if mode == "advantage":
          self.last_state = WIN
      else:
        greater_win(self)
    else:
      self.chaizhao_history.append("不通过")
      if less_win is None:
        if mode == "disadvantage":
          self.last_state = LOSS
      else:
        less_win(self)
  def last_dice_result(self):
    for x in reversed(self.dice_result_history):
      if type(x)  == type(int()):
        return x
    return
  def tail(self, x : int):
    return self.dice_history[-1][x]
  def syncalc_value(self, is_chaizhao : bool):
    if self.dice_this_turn is None:
      print(self)
    self.last_value = self.dice_this_turn + self.add
    if is_chaizhao:
      self.last_value += self.chaizhao_add
    else:
      self.last_value += self.situation_add
      self.last_value += sum(self.eternal_skill_plus.values())
    self.get_state(calc_value=False)
  def win_type(self):
    """n-直接获胜，c-拆招获胜"""
    if self.last_state != WIN and self.last_state != LOSS:
      return None
    if self.chaizhao_history is None: return "n"
    if self.chaizhao_history[-1] == "通过": return "c"
  def iter_skills(self, skill):
    """动态展开，后续会出现 GROUP 嵌套。"""
    if skill.type == ST_GROUP:
      for subskill in skill.sub_skills:
        yield from self.iter_skills(subskill)
    else:
      yield skill
  def __str__(self):
    return f"\
Game info:\nGreater player: {self.greater_player}\
\nLess player: {self.less_player}\
\nState list: {self.state_lst}\
\nDice history: {self.dice_history}\
\nDice result: {self.dice_result_history}\
\nState result: {self.state_history}\
\nFinal result: {self.value_history}\
\nExtra history: {self.chaizhao_history}"

# skills
def copy_attrs(
    src,
    dst,
    *,
    ignore: set[str] = None,
    deep: bool = False,
):
  if ignore is None:
    ignore = set()
  for name, value in vars(src).items():
    if name in ignore: continue
    if hasattr(dst, name):
      setattr(dst, name, deepcopy(value) if deep else value)
class Info:
  """
  the information data of a skill, used for communicating
  always be reset before calling, though not 100% done, you should not use it after calling
  """
  def __init__(self, privacy:bool = False):
    self.privacy = privacy
  def is_private(self):
    return self.privacy
  def set_attr(self, name : str, val : Any):
    setattr(self, name, val)
class forbidden_wrapper(type):
  def __new__(mcs, name, bases, namespace):
    original_call = namespace.get('__call__')
    if original_call:
      def wrapped_call(self, *args, **kwargs):
        if getattr(self, 'is_forbidden', False):
          return None
        return original_call(self, *args, **kwargs)
      namespace['__call__'] = wrapped_call
    return super().__new__(mcs, name, bases, namespace)
@dataclass(repr=False)
class base_skill(metaclass = forbidden_wrapper):
  is_forbidden:bool = False
  type:SkillType = ST_GROUP
  sub_skills:list = field(default_factory=list)
  info:Info = None
  info_black_list = {
    "info",
    "info_black_list",
    "checker",
    "callee",
    "callee_yes",
    "callee_no",
  }
  def __call__(self, g: game, is_greater: bool, is_chaizhao: bool):
    return "subclass must imply __call__"
  def __post_init__(self):
        pass  # 留给子类继承覆盖
  def __repr__(self):
    return self.__str__()
  def __str__(self):
    if self.type == ST_GROUP:
      s = ""
      for x in self.sub_skills:
        s += x.__str__()
      return f"({s})"
    else:
      return "subclass must imply __str__"
  def update_info(self):
    info = self.info
    if info is None: return
    for name in vars(self):
      if name in self.info_black_list: continue
      if hasattr(info, name):
        setattr(self, name, getattr(info, name))
  def set_attr(self, name:str, val):
    if not hasattr(self, name):
      raise AttributeError(
        f"{type(self).__name__} has no attribute '{name}'"
      )
    setattr(self, name, val)
    return self
  def copy_info_from(self, other, ignore:set = None, deep:bool = False):
    if not hasattr(other, "info") or other.info is None: return
    copy_attrs(
      dst=self.info, src=other.info,
      ignore=ignore, deep=deep
    )
  def set_info_attr(self, name : str, val : Any):
    if self.info is None: self.info = Info()
    setattr(self.info, name, val)
def forbid_skill(skill: base_skill):
  if skill.type == ST_GROUP:
    for subskill in skill.sub_skills:
      forbid_skill(subskill)
  else:
    skill.is_forbidden = True


@dataclass(repr=False)
class skill_qinggongyazhi(base_skill):
  def __post_init__(self):
    self.type = ST_ETERNAL_MODIFY_STATE
  def __call__(self, g: game, is_greater: bool, is_chaizhao: bool):
    if is_chaizhao:
      pass
    if g.turn == 0:
      if is_greater:
        turn_one_range(g.state_lst, DISADVANTAGE, DRAW)
      else:
        turn_one_range(g.state_lst, ADVANTAGE, DRAW)
  def __str__(self):
    return "轻功压制一阶"

# ===========================================================
# DSL System
# ===========================================================
Number = Union[bool, int, float, BattleRange]
def _to_expr(x):
  if x is None: return None
  if isinstance(x, Expr):
    return x
  if isinstance(x, (bool, int, float, BattleRange)) or x is None:
    return Const(value=x)
  if isinstance(x, list):
    return SeqExpr(items=x)
  raise TypeError(f"Cannot convert {type(x)} to Receiver")
def _flatten(x, g, is_greater, is_chaizhao, info):
  """递归地将 list 中所有元素 eval"""
  if isinstance(x, Expr):
    x = x.eval(g, is_greater, is_chaizhao, info)
  if isinstance(x, (list, tuple, set)):
    out = []
    for i in x:
      out.extend(_flatten(i, g, is_greater, is_chaizhao, info))
    return out
  return [x]
@dataclass(slots=True, frozen=False, repr=False, kw_only=True)
class Expr:
  def is_pure(self):
    return False
  def is_algebraic(self):
    return True
  def _compute(self,
           g : game,
           is_greater : bool = None,
           is_chaizhao : bool = None,
           info : Any = None):
    raise NotImplementedError
  def eval(self,
           g : game,
           is_greater : bool = None,
           is_chaizhao : bool = None,
           info : Any = None):
    if hasattr(self, "on_tick"):
      self.on_tick(g, is_greater, is_chaizhao, info)
    return self._compute(g, is_greater, is_chaizhao, info)
  def norm(self) -> "Expr":
    if not self.is_algebraic(): return self # 有状态无法规约
    return self._norm_recursive()
  def _norm_recursive(self) -> "Expr":
    return self  # 叶子默认不变
  def __add__(self, other):
    return Add(x=self, y=_to_expr(other)).norm()
  def __radd__(self, other):
    return Add(x=_to_expr(other), y=self).norm()
  def __sub__(self, other):
    return Sub(x=self, y=_to_expr(other)).norm()
  def __rsub__(self, other):
    return Sub(x=_to_expr(other), y=self).norm()
  def __mul__(self, other):
    return Mul(x=self, y=_to_expr(other)).norm()
  def __rmul__(self, other):
    return Mul(x=_to_expr(other), y=self).norm()
  def __truediv__(self, other):
    return Div(x=self, y=_to_expr(other)).norm()
  def __rtruediv__(self, other):
    return Div(x=_to_expr(other), y=self).norm()
  def __floordiv__(self, other):
    return FloorDiv(x=self, y=_to_expr(other)).norm()
  def __rfloordiv__(self, other):
    return FloorDiv(x=_to_expr(other), y=self).norm()
  def __mod__(self, other):
    return Mod(x=self, y=_to_expr(other)).norm()
  def __rmod__(self, other):
    return Mod(x=_to_expr(other), y=self).norm()
  def __neg__(self):
    return Neg(x=self).norm()
  def __gt__(self, other):
    return Gt(x=self, y=_to_expr(other)).norm()
  def __ge__(self, other):
    return Ge(x=self, y=_to_expr(other)).norm()
  def __lt__(self, other):
    return Lt(x=self, y=_to_expr(other)).norm()
  def __le__(self, other):
    return Le(x=self, y=_to_expr(other)).norm()
  def eq(self, other):
    return Eq(x=self, y=_to_expr(other)).norm()
  def ne(self, other):
    return Ne(x=self, y=_to_expr(other)).norm()
  # python 内部依赖，不能重载这两个
  def __and__(self, other):
    return And(x=self, y=_to_expr(other)).norm()
  def __or__(self, other):
    return Or(x=self, y=_to_expr(other)).norm()
  def __invert__(self):
    return Not(x=self).norm()
  def __repr__(self):
      return self.__str__()
  def __str__(self):
    return "[Subclass must imply __str__]"
  def isin(self, *others):
    if len(others) == 1: seq = others[0]
    else: seq = list(others)
    return InSet(x=self, candidates=seq).norm()
  def __pow__(self, other):
    return Pow(x=self, y=_to_expr(other)).norm()
  def __rpow__(self, other):
    return Pow(x=_to_expr(other), y=self).norm()
  def history(self, action=None, condition=None):
    if action is None: action = Append()
    return HistoryExpr(
      source=self,
      action=action,
      valid_when=HistoryGuard(condition)
    )
  def _runtime_list(self, g, is_greater = None, is_chaizhao = None, info = None):
    raise TypeError(f"{type(self).__name__} does not expose a runtime list")
  def len(self):
    return ExprListLen(self)
  def count(self, *vals):
    """
    无参数时，等价于 len。
    可以接受 list 或解包的 list。
    """
    if len(vals) == 0:
      return ExprListCount(target=self, val=None)
    if len(vals) == 1:
      return ExprListCount(target=self, val=vals[0])
    return ExprListCount(target=self, val=list(vals))
  def at(self, idx : int | Expr = -1):
    return ExprListVisitIndex(self, idx)
  def ifelse(self, command_if, command_else):
    return IfElse(cond=self, a=_to_expr(command_if), b = _to_expr(command_else))
  def map(self, *rules, default=None):
    cases = []
    if len(rules) == 1 and isinstance(rules[0], dict):
      rules = tuple(rules[0].items())
    for rule in rules:
      if not isinstance(rule, tuple) or len(rule) != 2:
        raise TypeError(
          "map rules must be pairs like (key, value), "
          "for example: x.map((1, 1), ({7, 8, 9}, 5))"
        )
      key, value = rule
      if key is None:
        cases.append(MapCase(
          key=None,
          value=_to_expr(value),
          mode="none"
        ))
      elif isinstance(key, (set, frozenset)):
        cases.append(MapCase(
          key=key,
          value=_to_expr(value),
          mode="in"
        ))
      else:
        cases.append(MapCase(
          key=_to_expr(key),
          value=_to_expr(value),
          mode="eq"
        ))
    return MapExpr(
      source=self,
      cases=cases,
      default=_to_expr(default) if default is not None else None
    )
@dataclass(slots=True, frozen=False, repr=False)
class Receiver(Expr):
  """静态表达式"""
  def is_pure(self):
    return True
@dataclass(slots=True, frozen=False, repr=False)
class DynamicExpr(Expr):
  """会在每次 eval 时产生新值/新行为的 Expr"""
  def is_pure(self):
    return False

@dataclass(slots=True, frozen=False, repr=False)
class ExprListLen(Expr):
  target : Expr = None
  def _compute(self, g, is_greater = None, is_chaizhao = None, info = None):
    self.target.eval(g, is_greater, is_chaizhao, info)
    return len(self
               .target
               ._runtime_list(g, is_greater, is_chaizhao, info))
@dataclass(slots=True, frozen=False, repr=False)
class ExprListCount(Expr):
  target: Expr = None
  val: Any = None
  def _compute(self, g, is_greater=None, is_chaizhao=None, info=None):
    self.target.eval(g, is_greater, is_chaizhao, info)
    lst = self.target._runtime_list(g, is_greater, is_chaizhao, info)
    t = Counter(lst)
    if self.val is None: return len(t)
    ret = 0
    for v in _flatten(self.val, g, is_greater, is_chaizhao, info):
      ret += t[v]
    return ret
@dataclass(slots=True, frozen=False, repr=False)
class ExprListVisitIndex(Expr):
  target : Expr = None
  num : int | Expr = None
  def _compute(self, g, is_greater = None, is_chaizhao = None, info = None):
    self.target.eval(g, is_greater, is_chaizhao, info)
    num = self.num
    if isinstance(num, Expr):
      num = num.eval(g, is_greater, is_chaizhao, info)
    lst = self.target._runtime_list(g, is_greater, is_chaizhao, info)
    if lst is None: return None
    if num < 0: num += len(lst)
    if num < 0 or num >= len(lst): return None
    x = lst[num]
    return x

@dataclass(slots=True, frozen=False, repr=False)
class ExprList(Expr):
  items: tuple[Expr, ...]
  def _runtime_list(self, g, is_greater = None, is_chaizhao = None, info = None):
    return self.items
  def _compute(self, g, is_greater=None, is_chaizhao=None, info=None):
    # 这里不 flatten！由于专门的 flatten 处理
    return [
        item.eval(g, is_greater, is_chaizhao, info)
        if isinstance(item, Expr) else item
        for item in self.items
    ]
  def __str__(self):
    return "[" + ", ".join(str(x) for x in self.items) + "]" 
def EList(*xs):
  return ExprList(tuple(_to_expr(x) for x in xs))


# ===========================================================
# History
# ===========================================================
@dataclass(slots=True, frozen=False, repr=False)
class HistoryAction:
  def apply(self, lst : list, val : Any):
    raise NotImplementedError
@dataclass(slots=True, frozen=False, repr=False)
class Append(HistoryAction):
  def apply(self, lst, val):
    lst.append(val)
@dataclass(slots=True, frozen=False, repr=False)
class Extend(HistoryAction):
  def apply(self, lst, val):
    lst.extend(val)
@dataclass(slots=True, frozen=False, repr=False)
class Replace(HistoryAction):
  def apply(self, lst, val):
    lst[:] = [val] if not isinstance(val, list) else val
@dataclass(slots=True, frozen=False, repr=False)
class Clear(HistoryAction):
  def apply(self, lst, val):
    lst.clear()
@dataclass(slots=True, frozen=False)
class HistoryGuard:
  condition: Expr | None = None
  def check(self, g : game, is_greater, is_chaizhao, info):
    if self.condition is None: return True
    return self.condition.eval(g, is_greater, is_chaizhao, info)
@dataclass(slots=True, repr=False)
class HistoryExpr(Expr):
  source: Expr = None
  action: HistoryAction = None
  valid_when: HistoryGuard = field(default_factory=HistoryGuard)
  memory: list = field(default_factory=list)
  def _runtime_list(self, g, is_greater = None, is_chaizhao = None, info = None):
    return self.memory
  def is_algebraic(self): # 有状态
    return False
  def is_pure(self):
    return False
  def on_tick(self, g : game, is_greater, is_chaizhao, info):
    if not self.valid_when.check(g, is_greater, is_chaizhao, info):
      return
    val = self.source.eval(g, is_greater, is_chaizhao, info)
    if val is None: return
    self.action.apply(self.memory, val)
  def _compute(self, g, ig, ic, info):
    return list(self.memory)
  def __str__(self):
    return f"H[{self.memory}]"

# ===========================================================
# Sequence
# ===========================================================
class SeqPolicy:
  def next(self,
           idx: int,
           n: int,
           g : game=None,
           is_greater : bool = None,
           is_chaizhao : bool = None,
           info : Any = None
           ) -> int | None:
    raise NotImplementedError
  def __str__(self):
    return "Some Unknown Seq Move Policy"
  def __repr__(self):
    return self.__str__()
class Loop(SeqPolicy):
  def next(self,
           idx: int,
           n: int,
           g : game=None,
           is_greater : bool = None,
           is_chaizhao : bool = None,
           info : Any = None
           ) -> int | None:
    return (idx + 1) % n
  def __str__(self):
    return "循环下标"
class StayTail(SeqPolicy):
  def next(self,
           idx: int,
           n: int,
           g : game=None,
           is_greater : bool = None,
           is_chaizhao : bool = None,
           info : Any = None
           ) -> int | None:
    return min(idx + 1, n - 1)
  def __str__(self):
    return "停留在尾部"
class Bounce(SeqPolicy):
  def __init__(self):
    self.dir = 1
  def next(self,
           idx: int,
           n: int,
           g : game=None,
           is_greater : bool = None,
           is_chaizhao : bool = None,
           info : Any = None
           ) -> int | None:
    if idx == n - 1: self.dir = -1
    if idx == 0: self.dir = 1
    return idx + self.dir
class Once(SeqPolicy):
  def next(self,
           idx: int,
           n: int,
           g : game=None,
           is_greater : bool = None,
           is_chaizhao : bool = None,
           info : Any = None
           ) -> int | None:
    if idx is None: return
    if idx == n - 1: return None
    else: return idx + 1
  def __str__(self):
    return "每次 +1"
class PerItemSeqPolicy(SeqPolicy):
  def __init__(self, actions):
    self.actions : list[SeqPolicy] = actions  # list[callable]
  def next(self,
           idx: int,
           n: int,
           g : game=None,
           is_greater : bool = None,
           is_chaizhao : bool = None,
           info : Any = None
           ) -> int | None:
    ig, ic = is_greater, is_chaizhao
    if idx >= n or idx < 0: return None
    return self.actions[idx].next(idx, n, g, ig, ic, info)
class OnceAsTurn(SeqPolicy):
  def next(self,
           idx: int,
           n: int,
           g : game=None,
           is_greater : bool = None,
           is_chaizhao : bool = None,
           info : Any = None
           ) -> int | None:
    i = Turn().eval(g, is_greater, is_chaizhao, info)
    return i if i < n else None
@dataclass(slots=True, repr=False)
class SeqExpr(Expr):
  items: list[Number | Expr]
  policy: SeqPolicy = field(default_factory=Once)
  idx: int = -1
  def _runtime_list(self, g, is_greater = None, is_chaizhao = None, info = None):
    return self.items
  def is_algebraic(self): return False
  def is_pure(self): return False
  def on_tick(self, g, is_greater, is_chaizhao, info):
    if self.idx is None: return # None means end
    self.idx = self.policy.next(
      self.idx,
      len(self.items),
      g,
      is_greater,
      is_chaizhao,
      info
    )
  def _compute(self, g, is_greater, is_chaizhao, info):
    if self.idx is None: return None # end
    val = self.items[self.idx]
    if isinstance(val, Expr):
      return val.eval(g, is_greater, is_chaizhao, info)
    return val
  def __str__(self):
    return f"[{self.items}: next=({self.policy})]"

@dataclass(slots=True, frozen=False, kw_only=True, repr=False)
class ReversableReceiver(Receiver):
  is_reverse : bool = False
  def _str_main(self):
    raise NotImplementedError
  def __str__(self):
    if self.is_reverse: return self._str_main() + "(自动取反)"
    else: return self._str_main() + "(永不取反)"
@dataclass(slots=True, frozen=False, kw_only=True, repr=False)
class ReversableExpr(Expr):
  is_reverse : bool = True
  def _str_main(self):
    raise NotImplementedError
  def __str__(self):
    if self.is_reverse: return self._str_main() + "(自动取反)"
    else: return self._str_main() + "(永不取反)"
@dataclass(slots=True, frozen=False, repr=False)
class Const(Receiver):
  """实现定义，因为不知道是用来干什么的所以不会变"""
  value : int | float | None = None
  def _compute(self,
           g : game,
           is_greater : bool = None,
           is_chaizhao : bool = None,
           info : Any = None):
    return self.value
  def __str__(self):
    return f"{self.value}"
@dataclass(slots=True, frozen=False, repr=False)
class Tail(ReversableReceiver, DynamicExpr):
  """x 反转为 11 - x，值域 [1,10]"""
  tail_id : int = 0
  def _compute(self,
           g : game,
           is_greater : bool = None,
           is_chaizhao : bool = None,
           info : Any = None):
    if not self.is_reverse:
      return g.tail(self.tail_id)
    else:
      x = g.tail(self.tail_id)
      return x if is_greater else num_reverse(x)
  def _str_main(self):
    if self.tail_id == 0: return "一尾"
    elif self.tail_id == 1: return "二尾"
    else: return "错误尾数"
@dataclass(slots=True, frozen=False, repr=False)
class LastDirectSum(Receiver):
  """实现定义，小方不进行任何改变"""
  def _compute(self, g, is_greater = None, is_chaizhao = None, info = None):
    return sum(g.dice_history[-1])
  def __str__(self):
    return "直和"
@dataclass(slots=True, frozen=False, repr=False)
class Turn(DynamicExpr):
  """
  回合数，从 0 开始有效。
  如果用 last_range_change，从 1 开始有效。
  """
  def _compute(self, g, is_greater = None, is_chaizhao = None, info = None):
    return g.turn
  def __str__(self):
    return "回合数"
@dataclass(slots=True, frozen=False, repr=False)
class LastDiceResult(ReversableReceiver, DynamicExpr):
  """自然定义，对小方取反。值域 [1,10]"""
  is_reverse : bool = True
  def _compute(self, g, is_greater = None, is_chaizhao = None, info = None):
    if self.is_reverse:
      return g.last_dice_result() if is_greater else num_reverse(g.last_dice_result())
    else:
      return g.last_dice_result()
  def _str_main(self):
    return "出目"
@dataclass(slots=True, frozen=False, repr=False)
class GameAddValue(ReversableExpr, DynamicExpr):
  """相对自身，对于小方取反"""
  def _compute(self, g, is_greater = None, is_chaizhao = None, info = None):
    if self.is_reverse:
      return g.add if is_greater else -g.add
    else:
      return g.add
  def _str_main(self):
    return "当前加值"
@dataclass(slots=True, frozen=False, repr=False)
class GameEternalAddValue(ReversableExpr, DynamicExpr):
  def _compute(self, g, is_greater = None, is_chaizhao = None, info = None):
    if self.is_reverse:
      return g.situation_add if is_greater else -g.situation_add
    else:
      return g.situation_add
  def _str_main(self):
    return "当前局势"
@dataclass(slots=True, frozen=False, repr=False)
class LastValue(DynamicExpr):
  """默认的结果，在 1~10 中"""
  def _compute(self, g, is_greater = None, is_chaizhao = None, info = None):
    return g.last_value
  def __str__(self):
    return "结果"
@dataclass(slots=True, frozen=False, repr=False)
class LastRange(ReversableExpr, DynamicExpr):
  def _compute(self, g, is_greater = None, is_chaizhao = None, info = None):
    if self.is_reverse:
      return g.last_state if is_greater else range_reverse(g.last_state)
    else:
      return g.last_state
  def _str_main(self):
    return f"结果区间"
@dataclass(slots=True, frozen=False, repr=False)
class RangeAt(ReversableExpr, DynamicExpr):
  """得到 num 对应的区间，取 0-9，超出直接 LOSS/WIN"""
  num : int | Expr = None
  def _get_range(self, g : game, is_greater, is_chaizhao, info):
    num = self.num
    if num is None: return None
    elif isinstance(num, int): num = num
    elif isinstance(num, Expr):
      num = num.eval(g, is_greater, is_chaizhao, info)
    else: raise TypeError(f"Type Error of num in {type(self).__name__}")
    if num is None: return None
    if num < 0: return LOSS
    elif num >= len(g.state_lst): return WIN
    else: return g.state_lst[num]
  def _compute(self, g, is_greater = None, is_chaizhao = None, info = None):
    s = self._get_range(g, is_greater, is_chaizhao, None)
    if self.is_reverse:
      return s if is_greater else range_reverse(s)
    else: return s
  def _str_main(self):
    return f"(区间 {self.num})"
@dataclass(slots=True, frozen=False, repr=False)
class TempRangeAt(ReversableExpr, DynamicExpr):
  num : int | Expr = None
  def _get_range(self, g : game, is_greater, is_chaizhao, info):
    num = self.num
    if num is None: return None
    elif isinstance(num, int): num = num
    elif isinstance(num, Expr):
      num = num.eval(g, is_greater, is_chaizhao, info)
    else: raise TypeError(f"Type Error of num in {type(self).__name__}")
    if num is None: return None
    if num < 0: return LOSS
    elif num >= len(g.tmp_state_lst): return WIN
    else: return g.tmp_state_lst[num]
  def _compute(self, g, is_greater = None, is_chaizhao = None, info = None):
    s = self._get_range(g, is_greater, is_chaizhao, None)
    if self.is_reverse:
      return s if is_greater else range_reverse(s)
    else: return s
  def _str_main(self):
    return f"(区间 {self.num})"
@dataclass(slots=True, frozen=False, repr=False)
class RandomUniform(DynamicExpr):
  lower_bound : int | Expr = None
  upper_bound : int | Expr = None
  def _compute(self, g, is_greater = None, is_chaizhao = None, info = None):
    def _gen(x):
      nonlocal g, is_greater, is_chaizhao, info
      if isinstance(x, int): return x
      elif isinstance(x, Expr):
        return x.eval(g, is_greater, is_chaizhao, info)
      else: raise TypeError(f"{x} is not a int or Receiver")
    lower_bound = _gen(self.lower_bound)
    upper_bound = _gen(self.upper_bound)
    if lower_bound is None or upper_bound is None: return None
    if upper_bound < lower_bound: return None
    return random.randint(lower_bound, upper_bound)
  def __str__(self):
    return f"在 [{self.lower_bound}, {self.upper_bound}] 间的均匀随机数"
@dataclass(slots=True, frozen=False, repr=False)
class RandomDict(DynamicExpr):
  pro_expr : dict[float, Number | Expr] = field(default_factory=dict)
  def is_algebraic(self):
    return False
  def __post_init__(self):
    s = sum(self.pro_expr.keys())
    if abs(s - 1.0) > 1e-9:
      raise ValueError("probabilities must sum to 1.0")
    super().__post_init__()
  def _pick_expr(self):
    r = random.random()
    acc = 0.0
    for p, expr in self.pro_expr.items():
      acc += p
      if r <= acc:
        return expr
    # 浮点误差兜底
    return next(reversed(self.pro_expr.values()))
  def _compute(self, g, is_greater=None, is_chaizhao=None, info=None):
    chosen = self._pick_expr()
    if isinstance(chosen, Expr):
      return chosen.eval(g, is_greater, is_chaizhao, info)
    else:
      return chosen
  def __str__(self):
    return f"{self.pro_expr}"
@dataclass(slots=True, frozen=False, repr=False)
class RandomFloat(DynamicExpr):
  def _compute(self, g, is_greater = None, is_chaizhao = None, info = None):
    return random.random()
  def __str__(self):
    return "[0, 1] 间的随机数"
@dataclass(slots=True, frozen=False, repr=False)
class GameStateHistory(ReversableExpr, DynamicExpr):
  def _compute(self, g, is_greater = None, is_chaizhao = None, info = None):
    if not self.is_reverse: return g.state_history
    else:
      if is_greater: return g.state_history
      else: return [range_reverse(s) for s in g.state_history]
  def _str_main(self):
    return f"区间历史"
  def _runtime_list(self, g, is_greater=None, is_chaizhao=None, info=None):
    return self._compute(g, is_greater, is_chaizhao, info)
@dataclass(slots=True, frozen=False, repr=False)
class GameDiceHistory(DynamicExpr):
  """历史尾号，不可反转"""
  def _compute(self, g, is_greater = None, is_chaizhao = None, info = None):
    return g.dice_history
  def _runtime_list(self, g, is_greater=None, is_chaizhao=None, info=None):
    return self._compute(g, is_greater, is_chaizhao, info)
@dataclass(slots=True, frozen=False, repr=False)
class GameDiceResultHistory(ReversableExpr, DynamicExpr):
  def _compute(self, g, is_greater = None, is_chaizhao = None, info = None):
    if not self.is_reverse: return g.dice_result_history
    else:
      if is_greater: return g.dice_result_history
      else: return [num_reverse(i) for i in g.dice_result_history]
  def _str_main(self):
    return "出目历史"
  def _runtime_list(self, g, is_greater=None, is_chaizhao=None, info=None):
    return self._compute(g, is_greater, is_chaizhao, info)
@dataclass(slots=True, frozen=False, repr=False)
class FindRange(ReversableExpr, DynamicExpr):
  """
  找到指定类型的 range,
  find_order = 0 从小到大；= 1 逆序，会反转；=2，随机顺序
  """
  find_range : BattleRange | list[Expr] | Expr | None = None
  find_order : int | list[Expr] = 0
  def _compute(self, g, is_greater = None, is_chaizhao = None, info = None):
    r = self.find_range
    if isinstance(r, Expr):
      r = r.eval(g, is_greater, is_chaizhao, info)
    if isinstance(r, list):
      t = [s.eval(g, is_greater, is_chaizhao, info) if isinstance(s, Expr) else s for s in r]
      r = t
    if r is None: return None # 有可能 eval 出来是 None
    o = self.find_order
    if self.is_reverse and not is_greater and isinstance(o, int):
      if isinstance(r, list):
        r = [range_reverse(x) for x in r]
      else:
        r = range_reverse(r)
      o = 1 - o # 反转
    if o == 0: flst = range(0, len(g.state_lst))
    elif o == 1: flst = reversed(range(0, len(g.state_lst)))
    elif o == 2:
      flst = list(range(0, len(g.state_lst)))
      random.shuffle(flst)
    elif isinstance(o, list):
      flst = [i.eval(g, is_greater, is_chaizhao, info) if isinstance(i, Expr) else i for i in o]
    for i in flst:
      if isinstance(r, list) and g.state_lst[i] in r:
        return i
      elif g.state_lst[i] == r:
        return i
  def _str_main(self):
    if self.find_order == 0: s = "从小到大"
    elif self.find_order == 1: s = "从大到小"
    elif self.find_order == 2: s = "随机顺序"
    else : s = self.find_order # 不知道是什么，自动解析
    return f"(按 {s} 的顺序在 state_list 找到第一个 {self.find_order})"
@dataclass(slots=True, frozen=False, repr=False)
class FindTempRange(ReversableExpr, DynamicExpr):
  """
  找到指定类型的 range, 
  find_order = 0 从小到大；= 1 逆序，会反转；=2 随机顺序
  """
  find_range : BattleRange | list[Expr] | Expr | None = None
  find_order : int | list[Expr] = 0
  def _compute(self, g, is_greater = None, is_chaizhao = None, info = None):
    r = self.find_range
    if isinstance(r, Expr):
      r = r.eval(g, is_greater, is_chaizhao, info)
    if isinstance(r, list):
      t = [s.eval(g, is_greater, is_chaizhao, info) if isinstance(s, Expr) else s for s in r]
      r = t
    if r is None: return None # 有可能 eval 出来是 None
    o = self.find_order
    if self.is_reverse and not is_greater and isinstance(o, int):
      if isinstance(r, list):
        r = [range_reverse(x) for x in r]
      else:
        r = range_reverse(r)
      o = 1 - o # 反转
    if o == 0: flst = range(0, len(g.tmp_state_lst))
    elif o == 1: flst = reversed(range(0, len(g.tmp_state_lst)))
    elif o == 2:
      flst = list(range(0, len(g.state_lst)))
      random.shuffle(flst)
    elif isinstance(o, list):
      flst = [i.eval(g, is_greater, is_chaizhao, info) if isinstance(i, Expr) else i for i in o]
    for i in flst:
      if isinstance(r, list) and g.tmp_state_lst[i] in r:
        return i
      elif g.tmp_state_lst[i] == r:
        return i
  def _str_main(self):
    if self.find_order == 0: s = "从小到大"
    elif self.find_order == 1: s = "从大到小"
    elif self.find_order == 2: s = "随机顺序"
    else : s = self.find_order # 不知道是什么，自动解析
    return f"(按 {s} 的顺序在 tmp_state_list 找到第一个 {self.find_order})"
@dataclass(slots=True, frozen=False, repr=False)
class GameEternalSkillPlus(ReversableExpr, DynamicExpr):
  """不需要区别正负，会自动取反。"""
  def _compute(self, g, is_greater=None, is_chaizhao=None, info=None):
    val = g.last_eternal_skill_plus
    if self.is_reverse:
      return val if is_greater else -val
    return val
  def _str_main(self):
    return "永久技能加值"
@dataclass(slots=True, frozen=False, repr=False)
class EternalSkillPlusAt(ReversableExpr, DynamicExpr):
  """
  暂时废弃，请不要使用
  某个技能带来的永久加值
  """
  skill_name: str = None
  def _compute(self, g, is_greater=None, is_chaizhao=None, info=None):
    if self.skill_name is None: return 0
    val = g.eternal_skill_plus[self.skill_name]
    if self.is_reverse: return val if is_greater else -val
    else:               return val
  def _str_main(self):
    return f"[永久技能加值: {self.skill_name}]"

# ===========================================================
# Counter
# ===========================================================
class Side(Enum):
  SELF = 0
  OPPONENT = 1
  BOTH = 2
  GLOBAL = 3
  def __str__(self):
    if self.value == 0 : return "自己"
    elif self.value == 1 : return "对方"
    elif self.value == 2 : return "双方"
    else: return "全局"
  def __repr__(self):
    return self.__str__()
class TurnType(Enum):
  ANY = 0
  FIGHT = 1
  CHAIZHAO = 2
  CURRENT = 3
  NOT_CURRENT = 4
  def __str__(self):
    if self.value == 0 : return "任意"
    elif self.value == 1 : return "非拆招"
    elif self.value == 2 : return "拆招"
    elif self.value == 3 : return "当前"
    elif self.value == 4 : return "与当前相反"
  def __repr__(self):
    return self.__str__()
@dataclass(slots=True, frozen=False, repr=False)
class CounterValue(DynamicExpr):
  name: str = None
  side: Side = Side.SELF
  turn_type: TurnType = TurnType.ANY
  def _key(self, name, side, mode):
    return (name, side, mode)
  def _compute(self, g, is_greater=None, is_chaizhao=None, info=None):
    if self.name is None: return 0
    if self.side == Side.SELF:
      sides = [is_greater]
    elif self.side == Side.OPPONENT:
      sides = [not is_greater]
    elif self.side == Side.BOTH:
      sides = [GREATER, LESS]
    elif self.side == Side.GLOBAL:
      sides = [None]

    if self.turn_type == TurnType.ANY:
      modes = [False, True]
    elif self.turn_type == TurnType.FIGHT:
      modes = [False]
    elif self.turn_type == TurnType.CHAIZHAO:
      modes = [True]
    elif self.turn_type == TurnType.CURRENT:
      modes = [is_chaizhao]
    elif self.turn_type == TurnType.NOT_CURRENT:
      modes = [not is_chaizhao]
    ans = 0
    for side in sides:
      for mode in modes:
        ans += g.game_counter[(self.name, side, mode)]
    return ans
  def __str__(self):
    return f"计数器[{self.name}, {self.side}, {self.turn_type}]"
@dataclass(slots=True, frozen=False, repr=False)
class TriggerCounter(DynamicExpr):
  skill_name: str = None
  side: Side = Side.SELF
  turn_type: TurnType = TurnType.ANY
  def _compute(self, g, is_greater=None, is_chaizhao=None, info=None):
    if self.skill_name is None:
      return 0
    return CounterValue(
      name=f"trigger:{self.skill_name}",
      side=self.side,
      turn_type=self.turn_type
    ).eval(g, is_greater, is_chaizhao, info)
  def __str__(self):
    return f"技能[{self.skill_name}, {self.side}, {self.turn_type}]的触发次数"
@dataclass(slots=True, frozen=False, repr=False)
class CounterAction:
  name: str = None
  side: Side = Side.SELF
  turn_type: TurnType = TurnType.CURRENT
  def _get_side_and_mode(self, g, is_greater, is_chaizhao, info):
    if self.side == Side.SELF:       side = is_greater
    elif self.side == Side.OPPONENT: side = not is_greater
    elif self.side == Side.GLOBAL  : side = None
    else : raise ValueError(f"{self.side} must be SELF/OPPOENT/GLOBAL")
    if self.turn_type == TurnType.ANY:
      raise ValueError(f"Counter Action turn_type can not be ANY!")
    elif self.turn_type == TurnType.FIGHT:
      mode = False
    elif self.turn_type == TurnType.CHAIZHAO:
      mode = True
    elif self.turn_type == TurnType.CURRENT:
      mode = is_chaizhao
    elif self.turn_type == TurnType.NOT_CURRENT:
      mode = not is_chaizhao
    return (side, mode)
  def apply(self, g, is_greater, is_chaizhao, info):
    raise NotImplementedError
  def _str_main(self):
    raise NotImplementedError
  def __str__(self):
    return f"将 ({self.name}, {self.side}, {self.turn_type}) 执行 {self._str_main()}"
  def __repr__(self):
    return self.__str__()
@dataclass(slots=True, frozen=False, repr=False)
class CounterAdd(CounterAction):
  value : int | Expr | None = None
  def apply(self, g, is_greater, is_chaizhao, info):
    val = self.value
    if isinstance(val, Expr):
      val = val.eval(g, is_greater, is_chaizhao, info)
    if val is None: return
    if not isinstance(val, int):
      raise TypeError(f"Counter Add value must be int, got {val}")
    side, mode = self._get_side_and_mode(g, is_greater, is_chaizhao, info)
    g.game_counter[(self.name, side, mode)] += val
  def _str_main(self):
    return f"增加 {self.value}"
@dataclass(slots=True, frozen=False, repr=False)
class CounterSet(CounterAction):
  value : int | Expr | None = None
  def apply(self, g, is_greater, is_chaizhao, info):
    val = self.value
    if isinstance(val, Expr):
      val = val.eval(g, is_greater, is_chaizhao, info)
    if val is None: return
    if not isinstance(val, int):
      raise TypeError(f"Counter Set value must be int, got {val}")
    side, mode = self._get_side_and_mode(g, is_greater, is_chaizhao, info)
    g.game_counter[(self.name, side, mode)] = val
  def _str_main(self):
    return f"设置为 {self.value}"
@dataclass(slots=True, frozen=False, repr=False)
class Unary(Expr):
  x: Expr = None
  def _norm(self, x):
    return self
  def _norm_recursive(self):
    x = self.x.norm()
    return self._norm(x)
@dataclass(slots=True, frozen=False, repr=False)
class Binary(Expr):
  x: Expr = None
  y: Expr = None
  def _norm(self, a, b):
    return self
  def _norm_recursive(self):
    x = self.x.norm()
    y = self.y.norm()
    return self._norm(x, y)
@dataclass(slots=True, frozen=False, repr=False)
class BoolBinary(Binary):
  def _compute(self, g, is_greater=None, is_chaizhao=None, info=None):
    raise NotImplementedError
def _is_const_num(r: Expr) -> bool:
  return isinstance(r, Const) and\
    isinstance(r.value, (bool, int, float, BattleRange))
def _const_val(r: Expr) -> Number:
  assert isinstance(r, Const)
  return r.value # type: ignore
@dataclass(slots=True, frozen=False, repr=False)
class Add(Binary):
  def _compute(self, g, is_greater = None, is_chaizhao = None, info = None):
    a = self.x.eval(g, is_greater, is_chaizhao, info)
    b = self.y.eval(g, is_greater, is_chaizhao, info)
    return None if a is None or b is None else a + b
  def _norm(self, a, b):
    if _is_const_num(a) and _is_const_num(b):
      return Const(value=_const_val(a) + _const_val(b))
    elif _is_const_num(b) and _const_val(b) == 0:
      return a
    elif _is_const_num(a) and _const_val(a) == 0:
      return b
    else:
      return Add(x=a, y=b)
  def __str__(self):
    return f"({self.x} + {self.y})"
@dataclass(slots=True, frozen=False, repr=False)
class Neg(Unary):
  def _compute(self, g, is_greater = None, is_chaizhao = None, info = None):
    x = self.x.eval(g, is_greater, is_chaizhao, info)
    return None if x is None else -x
  def _norm(self, x):
    if _is_const_num(x):
      return Const(value = -_const_val(x))
    elif isinstance(x, Neg):
      return x.x # 双重负号
    else:
      return Neg(x=x)
  def __str__(self):
    return f"-{self.x}"
@dataclass(slots=True, frozen=False, repr=False)
class Sub(Binary):
  def _compute(self, g, is_greater = None, is_chaizhao = None, info = None):
    a = self.x.eval(g, is_greater, is_chaizhao, info)
    b = self.y.eval(g, is_greater, is_chaizhao, info)
    return None if a is None or b is None else a - b
  def _norm(self, a, b):
    if _is_const_num(a) and _is_const_num(b):
      return Const(value=_const_val(a) - _const_val(b))
    elif _is_const_num(b) and _const_val(b) == 0:
      return a
    elif _is_const_num(a) and _const_val(a) == 0:
      return Neg(x=b) # -b
    else:
      return Sub(x=a, y=b)
  def __str__(self):
    return f"({self.x} - {self.y})"
@dataclass(slots=True, frozen=False, repr=False)
class Mul(Binary):
  def _compute(self, g, is_greater = None, is_chaizhao = None, info = None):
    a = self.x.eval(g, is_greater, is_chaizhao, info)
    b = self.y.eval(g, is_greater, is_chaizhao, info)
    return None if a is None or b is None else a * b
  def _norm(self, a, b):
    if _is_const_num(a) and _is_const_num(b):
      return Const(_const_val(a) * _const_val(b))
    if _is_const_num(a):
      if _const_val(a) == 0:
        return Const(0)
      if _const_val(a) == 1: return b
    if _is_const_num(b):
      if _const_val(b) == 0:
        return Const(0)
      if _const_val(b) == 1: return a
    return Mul(x=a, y=b)
  def __str__(self):
    return f"({self.x} * {self.y})"
@dataclass(slots=True, frozen=False, repr=False)
class Div(Binary):
  def _compute(self, g, is_greater = None, is_chaizhao = None, info = None):
    a = self.x.eval(g, is_greater, is_chaizhao, info)
    b = self.y.eval(g, is_greater, is_chaizhao, info)
    return None if a is None or b is None else a / b
  def _norm(self, a, b):
    if _is_const_num(a) and _is_const_num(b):
      return Const(value = _const_val(a) / _const_val(b))
    if _is_const_num(a) and _const_val(a) == 0:
      return Const(0)
    if _is_const_num(b) and _const_val(b) == 1:
      return a
    return Div(x=a, y=b)
  def __str__(self):
    return f"({self.x} / {self.y})"
@dataclass(slots=True, frozen=False, repr=False)
class FloorDiv(Binary):
  def _compute(self, g, is_greater = None, is_chaizhao = None, info = None):
    a = self.x.eval(g, is_greater, is_chaizhao, info)
    b = self.y.eval(g, is_greater, is_chaizhao, info)
    return None if a is None or b is None else a // b
  def _norm(self, a, b):
    if _is_const_num(a) and _is_const_num(b):
      return Const(value = _const_val(a) // _const_val(b))
    if _is_const_num(a) and _const_val(a) == 0:
      return Const(0)
    if _is_const_num(b) and _const_val(b) == 1:
      return a
    return FloorDiv(x=a, y=b)
  def __str__(self):
    return f"({self.x} // {self.y})"
@dataclass(slots=True, frozen=False, repr=False)
class Mod(Binary):
  def _compute(self, g, is_greater = None, is_chaizhao = None, info = None):
    a = self.x.eval(g, is_greater, is_chaizhao, info)
    b = self.y.eval(g, is_greater, is_chaizhao, info)
    return None if a is None or b is None else a % b
  def _norm(self, a, b):
    if _is_const_num(a) and _is_const_num(b):
      return Const(value = _const_val(a) % _const_val(b))
    if _is_const_num(a) and _const_val(a) == 0:
      return Const(0)
    if _is_const_num(b) and _const_val(b) == 1:
      return Const(0)
    return Mod(x=a, y=b)
  def __str__(self):
    return f"({self.x} % {self.y})"
@dataclass(slots=True, frozen=False, repr=False)
class Gt(BoolBinary):
  def _compute(self, g, is_greater=None, is_chaizhao=None, info=None):
    a = self.x.eval(g, is_greater, is_chaizhao, info)
    b = self.y.eval(g, is_greater, is_chaizhao, info)
    return None if a is None or b is None else a > b
  def __str__(self):
    return f"{self.x} 大于 {self.y}"
@dataclass(slots=True, frozen=False, repr=False)
class Ge(BoolBinary):
  def _compute(self, g, is_greater=None, is_chaizhao=None, info=None):
    a = self.x.eval(g, is_greater, is_chaizhao, info)
    b = self.y.eval(g, is_greater, is_chaizhao, info)
    return None if a is None or b is None else a >= b
  def __str__(self):
    return f"{self.x} 不小于 {self.y}"
@dataclass(slots=True, frozen=False, repr=False)
class Lt(BoolBinary):
  def _compute(self, g, is_greater=None, is_chaizhao=None, info=None):
    a = self.x.eval(g, is_greater, is_chaizhao, info)
    b = self.y.eval(g, is_greater, is_chaizhao, info)
    return None if a is None or b is None else a < b
  def __str__(self):
    return f"{self.x} 小于 {self.y}"
@dataclass(slots=True, frozen=False, repr=False)
class Le(BoolBinary):
  def _compute(self, g, is_greater=None, is_chaizhao=None, info=None):
    a = self.x.eval(g, is_greater, is_chaizhao, info)
    b = self.y.eval(g, is_greater, is_chaizhao, info)
    return None if a is None or b is None else a <= b
  def __str__(self):
    return f"{self.x} 不大于 {self.y}"
@dataclass(slots=True, frozen=False, repr=False)
class Eq(BoolBinary):
  def _compute(self, g, is_greater=None, is_chaizhao=None, info=None):
    a = self.x.eval(g, is_greater, is_chaizhao, info)
    b = self.y.eval(g, is_greater, is_chaizhao, info)
    return None if a is None or b is None else a == b
  def __str__(self):
    return f"{self.x} 和 {self.y} 相等"
@dataclass(slots=True, frozen=False, repr=False)
class Ne(BoolBinary):
  def _compute(self, g, is_greater=None, is_chaizhao=None, info=None):
    a = self.x.eval(g, is_greater, is_chaizhao, info)
    b = self.y.eval(g, is_greater, is_chaizhao, info)
    return None if a is None or b is None else a != b
  def __str__(self):
    return f"{self.x} 和 {self.y} 不相等"
@dataclass(slots=True, frozen=False, repr=False)
class And(BoolBinary):
  def _compute(self, g, is_greater=None, is_chaizhao=None, info=None):
    a = self.x.eval(g, is_greater, is_chaizhao, info)
    if a is False: return False
    if a is None: return None
    b = self.y.eval(g, is_greater, is_chaizhao, info)
    if a is None or b is None: return None
    return a and b
  def __str__(self):
    return f"[{self.x}] 且 [{self.y}]"
@dataclass(slots=True, frozen=False, repr=False)
class Or(BoolBinary):
  def _compute(self, g, is_greater=None, is_chaizhao=None, info=None):
    a = self.x.eval(g, is_greater, is_chaizhao, info)
    if a is True: return True
    if a is None: return None
    b = self.y.eval(g, is_greater, is_chaizhao, info)
    if a is None or b is None: return None
    return a or b
  def __str__(self):
    return f"[{self.x} 或 {self.y}]"
@dataclass(slots=True, frozen=False, repr=False)
class Not(Unary):
  def _compute(self, g, is_greater=None, is_chaizhao=None, info=None):
    x = self.x.eval(g, is_greater, is_chaizhao, info)
    return None if x is None else not x
  def __str__(self):
    return f"{self.x} 不成立"
@dataclass(slots=True, frozen=False, repr=False)
class InSet(Expr):
  x: Expr
  candidates: tuple[Expr, ...]
  def _compute(self, g, is_greater=None, is_chaizhao=None, info=None):
    val = self.x.eval(g, is_greater, is_chaizhao, info)
    candidates = _flatten(self.candidates, g, is_greater, is_chaizhao, info)
    return val in candidates
  def __str__(self):
    return f"{self.x} 属于 {self.candidates}"
@dataclass(slots=True, frozen=False, repr=False)
class Pow(Binary):
  def _compute(self, g, is_greater=None, is_chaizhao=None, info=None):
    a = self.x.eval(g, is_greater, is_chaizhao, info)
    b = self.y.eval(g, is_greater, is_chaizhao, info)
    return None if a is None or b is None else a ** b
  def _norm(self, a, b):
    if _is_const_num(a) and _is_const_num(b):
      return Const(_const_val(a) ** _const_val(b))
    if _is_const_num(b) and _const_val(b) == 1:
      return a
    if _is_const_num(b) and _const_val(b) == 0:
      return Const(1)
    if _is_const_num(a) and _const_val(a) == 1:
      return Const(1)
    if _is_const_num(a) and _const_val(a) == 0:
      return Const(0)
    return Pow(x=a, y=b)
  def __str__(self):
    return f"({self.x} 的 {self.y} 次方)"
@dataclass(slots=True, frozen=False, repr=False)
class IfElse(Expr):
    cond: Expr
    a: Expr
    b: Expr
    def _compute(self, g, is_greater=None, is_chaizhao=None, info=None):
      c = self.cond.eval(g, is_greater, is_chaizhao, info)
      if c is None: return None
      x = self.a.eval(g, is_greater, is_chaizhao, info)\
        if c else self.b.eval(g, is_greater, is_chaizhao, info)
      return x
    def __str__(self):
      return f"({self.cond} ? {self.a} : {self.b})"
@dataclass(slots=True, frozen=False, repr=False)
class MapCase:
  key: Any = None
  value: Expr = None
  mode: str = "eq"  # "eq", "in", "none"
  def match(self, source_expr, g, is_greater=None, is_chaizhao=None, info=None):
    if source_expr is None:
      return self.mode == "none" and self.key is None
    if self.mode == "none":
      return source_expr.eval(g, is_greater, is_chaizhao, info) is None
    if self.mode == "isin":
      return source_expr.isin(self.key).eval(
        g, is_greater, is_chaizhao, info
      ) is True
    # mode == "eq"
    return source_expr.eq(self.key).eval(
      g, is_greater, is_chaizhao, info
    ) is True
  def eval_value(self, g, is_greater=None, is_chaizhao=None, info=None):
    return self.value.eval(g, is_greater, is_chaizhao, info)
@dataclass(slots=True, frozen=False, repr=False)
class MapExpr(DynamicExpr):
  source: Expr = None
  cases: list[MapCase] = field(default_factory=list)
  default: Expr | None = None
  def is_algebraic(self):
    return False
  def _compute(self, g, is_greater=None, is_chaizhao=None, info=None):
    for case in self.cases:
      if case.match(self.source, g, is_greater, is_chaizhao, info):
        return case.eval_value(g, is_greater, is_chaizhao, info)
    if self.default is not None:
      return self.default.eval(g, is_greater, is_chaizhao, info)
    return None
  def __str__(self):
    parts = []
    for case in self.cases:
      if case.mode == "in":
        parts.append(f"若 {self.source} 在 {case.key} 中，则 {case.value}")
      else:
        parts.append(f"若 {self.source} == {case.key}，则 {case.value}")
    if self.default is not None:
      parts.append(f"否则 {self.default}")
    else:
      parts.append("否则 None")
    return "；".join(parts)

@dataclass(slots=True, frozen=False, repr=False)
class NotChaizhao(Expr):
  def eval(self, g, is_greater = None, is_chaizhao = None, info = None):
    return not is_chaizhao
  def __str__(self):
    return "非拆招"
@dataclass(slots=True, frozen=False, repr=False)
class IsChaizhao(Expr):
  def eval(self, g, is_greater = None, is_chaizhao = None, info = None):
    return is_chaizhao
  def __str__(self):
    return "拆招"
@dataclass(slots=True, frozen=False, repr=False)
class CastChaizhao(ReversableExpr, DynamicExpr):
  """
  由当前技能所属方发起一次拆招。
  num: 额外拆招加值
  difficulty: 拆招难度，为 None 则返回拆招值
  record: 是否记录到 g.chaizhao_history
  """
  num: int | Expr = 0
  difficulty: int | Expr | None = 5
  record: bool = True
  def _eval_num(self, x, g, is_greater, is_chaizhao, info):
    if isinstance(x, Expr):
      return x.eval(g, is_greater, is_chaizhao, info)
    return x
  def _compute(self, g, is_greater=None, is_chaizhao=None, info=None):
    if is_greater is None:
      raise ValueError("CastChaizhao requires is_greater")
    extra = self._eval_num(self.num, g, is_greater, is_chaizhao, info)
    if self.difficulty is not None:
      difficulty = self._eval_num(self.difficulty, g, is_greater, is_chaizhao, info)
    else: difficulty = None
    if extra is None: return False
    if not isinstance(extra, int): raise TypeError(f"extra in {self} must be int")
    if not isinstance(difficulty, int): raise TypeError(f"difficulty in {self} must be int")
    old_chaizhao_add = g.chaizhao_add
    old_skill_type = g.skill_type_now
    # 记录旧值，避免污染外部状态，可以回退到正常状态
    try:
      g.get_value(True) # 内部触发其他技能
      # 默认的 chaizhao 总是从 GREATER 视角的
      if is_greater: g.last_value += extra
      else:          g.last_value -= extra
      if len(g.value_history) > 0: g.value_history[-1] = g.last_value
      # 覆盖 get_value(True) 刚 append 的最后一个值。
      if difficulty is None:
        x = g.last_value
        x = x if (not self.is_reverse or is_greater) else 11 - x
        return x
      greater_pass = g.last_value > difficulty
      self_win = greater_pass if is_greater else not greater_pass
      if self.record:
        g.chaizhao_history.append("通过" if greater_pass else "不通过")
      return self_win
    finally:
      g.chaizhao_add = old_chaizhao_add
      g.skill_type_now = old_skill_type
  def __str__(self):
    return f"(发起一次拆招，额外加值 {self.num}，难度 {self.difficulty})"

@dataclass(repr=False)
class r_skill(base_skill):
  skill_name: str | None = None
  on_init: list[CounterAction] = field(default_factory=list)
  before_check: list[CounterAction] = field(default_factory=list)
  on_trigger: list[CounterAction] = field(default_factory=list)
  on_work_after: list[CounterAction] = field(default_factory=list)
  valid_when : Expr | bool = field(default_factory=NotChaizhao)
  def _exprify_fields(self, *args):
    """将参数 Expr 化"""
    for name in args:
      if hasattr(self, name):
        val = getattr(self, name)
        try: setattr(self, name, _to_expr(val))
        except TypeError: pass
  def __post_init__(self):
    self._exprify_fields("valid_when")
  def init_skill(self, g, is_greater: bool):
    for action in self.on_init:
      action.apply(g, is_greater, False, self.info)
  def _str_main(self):
    raise NotImplementedError
  def __str__(self):
    if self.valid_when is None: main_part = self._str_main()
    else: main_part = f"当 {self.valid_when} 时，{self._str_main()}"
    def decode_list(lst : list | None) -> str:
      if lst is None or len(lst) == 0: return None
      else:
        s = ""
        for x in lst: s += f"{x}, "
        return s.removesuffix(", ")
    p = ""
    s = decode_list(self.on_init)
    if s is not None: p = f"[初始时, {s}]; "
    s = decode_list(self.before_check)
    if s is not None: p = p + f"[判定开始前, {s}]; "
    s = decode_list(self.on_trigger)
    if s is not None: p = p + f"[触发时, {s}]; "
    s = decode_list(self.on_work_after)
    if s is not None: p = p + f"[结算完成后, {s}]; "
    return p + main_part
  def work(self, g:game, is_greater:bool, is_chaizhao:bool):
    raise KeyError(f"Subclass must imply work()")
  def __call__(self, g, is_greater, is_chaizhao):
    for action in self.before_check:
      action.apply(g, is_greater, is_chaizhao, self.info)
    checker = self.valid_when
    ok = False
    if checker is None: ok = True
    elif isinstance(checker, bool) and checker == True: ok = True
    elif isinstance(checker, Expr) and checker.eval(g, is_greater, is_chaizhao, self.info) == True:
      ok = True
    if ok:
      if self.skill_name is not None: # trigger once
        CounterAdd(
          name=f"trigger:{self.skill_name}",
          value=1
        ).apply(g, is_greater, is_chaizhao, self.info)
      for action in self.on_trigger:
        action.apply(g, is_greater, is_chaizhao, self.info)
      ret = self.work(g, is_greater, is_chaizhao)
      for action in self.on_work_after:
        action.apply(g, is_greater, is_chaizhao, self.info)
      return ret
    else: return None
  def eval(self,
           g : game,
           is_greater : bool = None,
           is_chaizhao : bool = None,
           info : Any = None):
    if isinstance(self.valid_when, bool):
      return self.valid_when
    else:
      return self.valid_when.eval(g, is_greater, is_chaizhao, info)
@dataclass(repr=False)
class rcall_plus(r_skill):
  num : int | Expr = None
  def __post_init__(self):
    super().__post_init__()
    self.type = ST_ADD
    self._exprify_fields("num")
  def work(self, g:game, is_greater:bool, is_chaizhao:bool):
    num = self.num
    if num is None: return
    if isinstance(num, Expr):
      num = num.eval(g, is_greater, is_chaizhao, self.info)
    if num is None: return
    if not isinstance(num, int):
      raise TypeError(f"Num of {type(self).__name__} is not int but {num}!")
    num = num if is_greater else -num
    g.add += num
  def _str_main(self):
    if isinstance(self.num, int):
      return f"获得无条件 {self.num:+d}"
    else:
      return f"获得 {self.num} 的加值"
@dataclass(repr=False)
class rcall_num_view_as(r_skill):
  num : int | Expr = None
  def __post_init__(self):
    super().__post_init__()
    self.type = ST_MODIFY_NUM
    self._exprify_fields("num")
  def work(self, g:game, is_greater:bool, is_chaizhao:bool):
    num = self.num
    if num is None: return
    if isinstance(num, Expr):
      num = num.eval(g, is_greater, is_chaizhao, self.info)
    if num is None: return
    if not isinstance(num, int):
      raise TypeError(f"Num of {type(self).__name__} is not int!")
    g.dice_result_history[-1] = num if is_greater else num_reverse(num)
    g.dice_this_turn = g.dice_result_history[-1]
    g.syncalc_value(is_chaizhao)
    g.get_state(calc_value=False)
  def _str_main(self):
    return f"出目视为 {self.num}"
@dataclass(repr=False, kw_only=True)
class rcall_count_plus(r_skill):
  """就是 eternal plus，但是使用自己的存储，不污染局势"""
  num : int | Expr = None
  _count : int = 0
  def __post_init__(self):
    super().__post_init__()
    self.type = ST_ADD
    self._exprify_fields("num")
  def work(self, g:game, is_greater:bool, is_chaizhao:bool):
    num = self.num
    if num is None: return
    if isinstance(num, Expr):
      num = num.eval(g, is_greater, is_chaizhao, self.info)
    if num is None: return
    if not isinstance(num, int):
      raise TypeError(f"Num of {type(self).__name__} is not int!")
    num = num if is_greater else -num
    self._count += num
    g.add += self._count
  def _str_main(self):
    s = ""
    if self._count != 0: s += f"初始获得 {self._count:+d}，"
    s += f"每回合获得 {self.num}"
    return s
@dataclass(repr=False, kw_only=True)
class rbase_range_change(r_skill):
  """整数表示偏移，区间表示视为"""
  arg : int | BattleRange | Expr = None
  source : Expr | BattleRange | None = None
  # 生成区间基准的方法
  is_reverse : bool = True
  # 是否翻转区间
  def __post_init__(self):
    super().__post_init__()
    if self.arg is None: raise NotImplementedError
    self._exprify_fields("arg", "source")
  def _default_range(self):
    raise NotImplementedError
  def _get_state(self, g : game, is_greater, is_chaizhao):
    s = self.source
    if s is None: s = self._default_range() # use default
    if isinstance(s, Expr): s = s.eval(g, is_greater, is_chaizhao, self.info)
    if not isinstance(s, BattleRange): raise TypeError(f"{s} is not a range?!")
    return s
  def _get_range(self, g : game, is_greater, is_chaizhao):
    s = self._get_state(g, is_greater, is_chaizhao)
    if s is None: return None
    arg = self.arg
    if isinstance(arg, Expr):
      arg = arg.eval(g, is_greater, is_chaizhao, self.info)
    if isinstance(arg, int):
      arg = arg if is_greater else -arg
      s = s + arg
    elif isinstance(arg, BattleRange):
      s = arg if is_greater else range_reverse(arg)
    else: raise TypeError(f"Arg of {type(self).__name__} is illegal")
    return s
  def _str_wrapper(self):
    arg = self.arg
    if isinstance(arg, int):
      if arg == 0: return "无效果"
      elif arg > 0: return f"抬档 {arg} 次"
      elif arg < 0: return f"降档 {-arg} 次"
    elif isinstance(arg, BattleRange):
      return f"视为 {arg}"
    else:
      return f"执行 [{arg}]"
  def _str_body(self):
    raise NotImplementedError
  def _str_main(self):
    return self._str_body() + self._str_wrapper()
@dataclass(repr=False)
class rcall_last_range_change(rbase_range_change):
  def __post_init__(self):
    super().__post_init__()
    self.type = ST_EXTRA_ATK
  def _default_range(self):
    return LastRange(is_reverse=self.is_reverse)
  def work(self, g, is_greater, is_chaizhao):
    x = self._get_range(g, is_greater, is_chaizhao)
    if x is None: pass
    else: g.last_state = x
  def _str_body(self):
    return "本回合结果"
@dataclass(repr=False)
class rcall_range_change(rbase_range_change):
  range_id : int | Expr = None
  def __post_init__(self):
    super().__post_init__()
    self.type = ST_ETERNAL_MODIFY_STATE
    self._exprify_fields("range_id")
  def _default_range(self):
    if not hasattr(self.info, "id"):
      raise ValueError(f"{self} do not have \"id\"!")
    return RangeAt(num=getattr(self.info, "id"), is_reverse=self.is_reverse)
  def work(self, g, is_greater, is_chaizhao):
    id = self.range_id
    if id is None: return
    elif isinstance(id, Expr):
      id = id.eval(g, is_greater, is_chaizhao, self.info)
    if id is None: return
    if not isinstance(id, int):
      raise TypeError(f"{id} is illegal")
    if id < 0 or id >= len(g.state_lst):
      raise BufferError(f"{id} is out of range!")
    self.set_info_attr("id", id)
    x = self._get_range(g, is_greater, is_chaizhao)
    if x is None: pass
    else: g.state_lst[id] = x
  def _str_body(self):
    return f"将 {self.range_id} 对应区间永久"
@dataclass(repr=False)
class rcall_temp_range_change(rbase_range_change):
  range_id : int | Expr = None
  def __post_init__(self):
    super().__post_init__()
    self.type = ST_MODIFY_STATE
    self._exprify_fields("range_id")
  def _default_range(self):
    if not hasattr(self.info, "id"):
      raise ValueError(f"{self} do not have \"id\"!")
    return TempRangeAt(num=getattr(self.info, "id"), is_reverse=self.is_reverse)
  def work(self, g, is_greater, is_chaizhao):
    id = self.range_id
    if id is None: return
    elif isinstance(id, Expr):
      id = id.eval(g, is_greater, is_chaizhao, self.info)
    if not isinstance(id, int):
      raise TypeError(f"{id} is illegal")
    if id < 0 or id >= len(g.tmp_state_lst):
      raise BufferError(f"{id} is out of range!")
    self.set_info_attr("id", id)
    x = self._get_range(g, is_greater, is_chaizhao)
    if x is None: pass
    else: g.tmp_state_lst[id] = x
  def _str_body(self):
    return f"将 {self.range_id} 对应区间临时"
@dataclass(repr=False, kw_only=True)
class rcall_eternal_plus(r_skill):
  """
  条件成立时，向 game 的 eternal effect pool 插入一个 Expr。
  pool 的 eval / 求和 / 删除由 game 统一负责。
  """
  num: int | Expr = None
  def __post_init__(self):
    super().__post_init__()
    self.type = ST_ADD
    self._exprify_fields("num")
    if self.skill_name is None:
      raise ValueError("rcall_eternal_plus requires skill_name")
  def work(self, g: game, is_greater: bool, is_chaizhao: bool):
    g.add_eternal_effect(
      skill_name=self.skill_name,
      expr=deepcopy(self.num),
      is_greater=is_greater,
      info=self.info,
    )
  def _str_main(self):
    return f"生成永久加值池效果 {self.num}"
@dataclass(repr=False, kw_only=True)
class rcall_armor(rcall_last_range_change):
  """
  护甲机制，本质是 rcall_last_range_change 的子类。
  消耗一层护甲抵消一次失败（变为均势），如果负数，每 -1 额外消耗一层。
  armor_name 是名字，不能重叠，但是自动增加 \"armor:\" 前缀。
  value 是初始护甲层数。
  armor_effect 是起效后的转化的类型（唯一的用处是提供缺省值），不应该再使用 self.arg。
  """
  armor_name: str = None
  value: int | Expr = 1
  armor_effect: int | BattleRange | Expr = DRAW
  def __post_init__(self):
    if self.armor_name is None:
      raise ValueError("rcall_armor requires armor_name")
    # 保留额外传入的 init / after hook
    user_on_init = list(self.on_init)
    user_on_work_after = list(self.on_work_after)
    # 保留额外传入的 valid_when
    user_valid_when = self.valid_when
    armor = CounterValue(
      name=f"armor:{self.armor_name}",
      turn_type=TurnType.FIGHT
    )
    cost = (LastValue() > 0).ifelse(
      1, 2 - LastValue()
    )
    armor_valid_when = (
      LastRange().isin(LOSS) & (armor >= cost)
    )
    if user_valid_when is None:
      self.valid_when = armor_valid_when
    elif user_valid_when is True:
      self.valid_when = armor_valid_when
    elif user_valid_when is False:
      self.valid_when = False
    else:
      self.valid_when = _to_expr(user_valid_when) & armor_valid_when
    self.arg = self.armor_effect
    self.on_init = [
      CounterSet(
        name=f"armor:{self.armor_name}",
        value=self.value,
        turn_type=TurnType.FIGHT
      )
    ] + user_on_init
    self.on_work_after = [
      CounterAdd(
        name=f"armor:{self.armor_name}",
        value=-cost,
        turn_type=TurnType.FIGHT
      )
    ] + user_on_work_after
    super().__post_init__()
  def _str_main(self):
    return f"(护甲[{self.armor_name}]，初始值 {self.value}，效果 [变为 {self.armor_effect}])"

def _empty_stats():
  return {
    "win": 0,
    "win_t": 0,
    "win_min_t": None,
    "win_max_t": None,
    "loss": 0,
    "loss_t": 0,
    "loss_min_t": None,
    "loss_max_t": None,
    "draw": 0,
    "total": 0,
  }
def _update_min_max(old_min, old_max, x):
  if old_min is None or x < old_min:
    old_min = x
  if old_max is None or x > old_max:
    old_max = x
  return old_min, old_max
def _merge_stats(a, b):
  a["win"] += b["win"]
  a["win_t"] += b["win_t"]
  a["loss"] += b["loss"]
  a["loss_t"] += b["loss_t"]
  a["draw"] += b["draw"]
  a["total"] += b["total"]
  if b["win_min_t"] is not None:
    a["win_min_t"], a["win_max_t"] = _update_min_max(
      a["win_min_t"], a["win_max_t"], b["win_min_t"]
    )
    a["win_min_t"], a["win_max_t"] = _update_min_max(
      a["win_min_t"], a["win_max_t"], b["win_max_t"]
    )
  if b["loss_min_t"] is not None:
    a["loss_min_t"], a["loss_max_t"] = _update_min_max(
      a["loss_min_t"], a["loss_max_t"], b["loss_min_t"]
    )
    a["loss_min_t"], a["loss_max_t"] = _update_min_max(
      a["loss_min_t"], a["loss_max_t"], b["loss_max_t"]
    )
  return a
def _simulate_stats(g: game, N: int = 100000, display: bool = False):
  stats = _empty_stats()
  stats["total"] = N
  if display:
    print(f"simulate {N} times")
    print(f"骰子: {g.dice}")
  for _ in range(N):
    t = deepcopy(g)
    state = BEGIN
    while t.turn < 100:
      state, turn = t.simulate_one_turn()
      if state == WIN:
        stats["win"] += 1
        stats["win_t"] += turn
        stats["win_min_t"], stats["win_max_t"] = _update_min_max(
          stats["win_min_t"], stats["win_max_t"], turn
        )
        break
      elif state == LOSS:
        stats["loss"] += 1
        stats["loss_t"] += turn
        stats["loss_min_t"], stats["loss_max_t"] = _update_min_max(
          stats["loss_min_t"], stats["loss_max_t"], turn
        )
        break
    if state != WIN and state != LOSS:
      stats["draw"] += 1
    if N < 10 and display:
      print(t)
  return stats
def _stats_to_result(stats):
  N = stats["total"]
  win = stats["win"]
  loss = stats["loss"]
  draw = stats["draw"]
  win_rate = win / N if N else 0
  loss_rate = loss / N if N else 0
  draw_rate = draw / N if N else 0
  win_turn = stats["win_t"] / win if win != 0 else 0
  loss_turn = stats["loss_t"] / loss if loss != 0 else 0
  return (
    (win_rate, win_turn, stats["win_min_t"], stats["win_max_t"]),
    (loss_rate, loss_turn, stats["loss_min_t"], stats["loss_max_t"]),
    draw_rate
  )
def simulate(g: game, N: int = 100000, display:bool = True):
  start_time = time.time()
  # if display:
  #   print(f"simulate {N} times")
  #   print(f"骰子: {g.dice}")
  stats = _simulate_stats(g, N, display=display)
  result = _stats_to_result(stats)
  (win_rate, win_turn, win_min_t, win_max_t), (loss_rate, loss_turn, loss_min_t, loss_max_t), draw_rate = result
  end_time = time.time()
  if display:
    print(f"耗时: {end_time - start_time} second")
    print(
      f"Greater player: {g.greater_player}\n"
      f"win rate: {win_rate}, "
      f"average win turn: {win_turn}\n"
      f"min win turn: {win_min_t}, "
      f"max win turn: {win_max_t}"
    )
    print(
      f"Less player: {g.less_player}\n"
      f"win rate: {loss_rate}, "
      f"average win turn: {loss_turn}\n"
      f"min win turn: {loss_min_t}, "
      f"max win turn: {loss_max_t}"
    )
    print(f"draw rate: {draw_rate}")
  return result
def _simulate_worker(arg):
  inner_g, n = arg
  return _simulate_stats(deepcopy(inner_g), n, display=False)
def simulate_batch_one_game(
  generator: Callable[[Any], game] | game,
  param: Any | None = None,
  N: int = 100_000,
  worker_num: int = 4,
  display: bool = True
):
  begin_time = time.time()
  if type(generator) == game:
    g = generator
  else:
    if param is None:
      g = generator()
    else:
      g = generator(param)
  if worker_num is None or worker_num <= 0 or worker_num > cpu_count():
    worker_num = 1
  worker_num = min(worker_num, N)
  base = N // worker_num
  rem = N % worker_num
  chunks = [
    base + (1 if i < rem else 0)
    for i in range(worker_num)
  ]
  tasks = [(g, chunk) for chunk in chunks if chunk > 0]
  if display:
    print(f"simulate_batch: N={N}, workers={len(tasks)}")
  total_stats = _empty_stats()
  with Pool(len(tasks)) as pool:
    results = pool.map(_simulate_worker, tasks)
  for s in results:
    _merge_stats(total_stats, s)
  result = _stats_to_result(total_stats)
  (win_rate, win_turn, win_min_t, win_max_t), (loss_rate, loss_turn, loss_min_t, loss_max_t), draw_rate = result
  end_time = time.time()
  if display:
    print(f"用时: {end_time - begin_time} second")
    print(f"骰子: {g.dice}")
    print(
      f"Greater player: {g.greater_player}\n"
      f"win rate: {win_rate}, "
      f"average win turn: {win_turn}\n"
      f"min win turn: {win_min_t}, "
      f"max win turn: {win_max_t}"
    )
    print(
      f"Less player: {g.less_player}\n"
      f"win rate: {loss_rate}, "
      f"average win turn: {loss_turn}\n"
      f"min win turn: {loss_min_t}, "
      f"max win turn: {loss_max_t}"
    )
    print(f"draw rate: {draw_rate}")
  return result

def simulate_game_auto_batch(
  generator : Callable[[Any], game] | game,
  param : Any | None = None,
  confidence_level : float = 0.99,
  deviation : float = 0.005,
  worker_num : int = 4,
  display : bool = True,
  simulate_num : int = 0
):
  if simulate_num == 0:
    alpha = 1 - confidence_level
    N = math.ceil(math.log(2 / alpha) / (2 * deviation * deviation))
  else:
    N = simulate_num
  simulate_batch_one_game(generator, param, N, worker_num, display)