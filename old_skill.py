from skill import *

def forbid_skill(skill: base_skill):
  if skill.type == ST_GROUP:
    for subskill in skill.sub_skills:
      forbid_skill(subskill)
  else:
    skill.is_forbidden = True
@dataclass(repr=False)
class skill_plus(base_skill):
  num:int = 1
  def __post_init__(self):
    self.type = ST_ADD
  def __call__(self, g: game, is_greater: bool, is_chaizhao: bool):
    if is_chaizhao: return
    if is_greater: g.add += self.num
    else: g.add -= self.num
  def __str__(self):
    if self.num == 0:
      return "pass"
    elif self.num > 0:
      return f"(无条件 +{self.num}, 于拆招中无效)"
    else:
      return f"(无条件 {self.num}, 于拆招中无效)"
@dataclass(repr=False)
class skill_yiquantulv(base_skill):
  def __post_init__(self):
    self.type = ST_MODIFY_STATE
  def __call__(self, g: game, is_greater: bool, is_chaizhao: bool):
    if is_chaizhao or g.turn > 1:
      return
    if is_greater:
      g.tmp_state_lst[8] = WIN
    else:
      g.tmp_state_lst[1] = LOSS
  def __str__(self):
    return "(第一个回合，你的获胜区间+1)"
@dataclass(repr=False)
class skill_tianxingyuanman(base_skill):
  def __post_init__(self):
    self.type = ST_ADD
  def __call__(self, g: game, is_greater: bool, is_chaizhao: bool):
    if is_chaizhao:
      return
    if is_greater:
      g.add += g.turn
    else:
      g.add -= g.turn
  def __str__(self):
    return "(每回合获得+1，第一回合+0)"
@dataclass(repr=False)
class skill_wgu1(base_skill):
  def __post_init__(self):
    self.type = ST_GET_NUM
  def __call__(self, g: game, is_greater: bool, is_chaizhao: bool):
    if is_chaizhao:
      return
    if is_greater:
      return max(g.dice_history[-1])
    else:
      return min(g.dice_history[-1])
  def __str__(self):
    return "(你的出目为所有骰子中的最值)"
@dataclass(repr=False)
class skill_wgu2(base_skill):
  def __post_init__(self):
    self.type = ST_ROLL_DICE
    self.cnt = 0
  def __call__(self, g: game, is_greater: bool, is_chaizhao: bool):
    # print(f"  # begin {g.turn}")
    if is_chaizhao:
      return
    if is_greater:
      for x in g.dice_history[-1]:
        if x == 1:
          self.cnt += 1
    else:
      for x in g.dice_history[-1]:
        if x == 10:
          self.cnt += 1
    for _ in range(self.cnt):
      g.dice_history[-1].append(g.dice())
    # print(f"  # end:{self.cnt}, {g.dice_history[-1]}, {g.dice_history}")
  def __str__(self):
    return "(每出现一个失败骰，你获得一个骰子)"
@dataclass(repr=False)
class skill_wgu3(base_skill):
  def __post_init__(self):
    self.type = ST_ETERNAL_MODIFY_STATE
  def __call__(self, g: game, is_greater: bool, is_chaizhao: bool):
    if is_chaizhao:
      return
    flg = True
    if is_greater:
      for x in g.dice_history[-1]:
        if x != g.last_value:
          g.state_lst[x - 1] = range_uplevel(g.state_lst[x - 1])
        elif flg == False:
          g.state_lst[x - 1] = range_uplevel(g.state_lst[x - 1])
        else:
          flg = False
    else:
      for x in g.dice_history[-1]:
        if x != g.last_value:
          g.state_lst[x - 1] = range_declevel(g.state_lst[x - 1])
        elif flg == False:
          g.state_lst[x - 1] = range_declevel(g.state_lst[x - 1])
        else:
          flg = False
  def __str__(self):
    return "(非最终结果的出目提高一档（总是对你有利）)"
@dataclass(repr=False)
class skill_wgu(base_skill):
  def __post_init__(self):
    self.type = ST_GROUP
    self.sub_skills = [skill_wgu1(), skill_wgu2(), skill_wgu3()]
@dataclass(repr=False)
class skill_jianxujili_70(base_skill):
  def __post_init__(self, trigger_range: int = 2):
    self.type = ST_EXTRA_ATK
    self.is_greater = GREATER
    self.trigger_range = trigger_range
  def hurt_enemy(self, g: game):
    if self.is_greater:
      g.last_state = ADVANTAGE
    else:
      g.last_state = DISADVANTAGE
  def __call__(self, g: game, is_greater: bool, is_chaizhao: bool):
    if is_chaizhao:
      return
    self.is_greater = is_greater
    if is_greater:
      if 1 <= g.last_dice_result() <= self.trigger_range:
        g.dice_result_history.append("大点方见虚70拆招")
        g.chaizhao(greater_win = self.hurt_enemy)
    else:
      if 11 - self.trigger_range <= g.last_dice_result() <= 10:
        g.dice_result_history.append("小点方见虚70拆招")
        g.chaizhao(less_win = self.hurt_enemy)
  def __str__(self):
    return "(当骰子出目为 1/2 时，进行一次拆招，通过则变为你的上风)"
@dataclass(repr=False)
class skill_jianxujili_100(base_skill):
  def __post_init__(self):
    self.type = ST_EXTRA_ATK
    self.is_greater = GREATER
  def hurt_enemy(self, g: game):
    if self.is_greater:
      g.last_state = ADVANTAGE
    else:
      g.last_state = DISADVANTAGE
  def __call__(self, g: game, is_greater: bool, is_chaizhao: bool):
    if is_chaizhao:
      return
    self.is_greater = is_greater
    if is_greater:
      if 1 <= g.last_dice_result() <= 2:
        g.dice_result_history.append("大点方见虚100拆招")
        g.chaizhao(greater_win = self.hurt_enemy, difficulty = 0)
    else:
      if 9 <= g.last_dice_result() <= 10:
        g.dice_result_history.append("小点方见虚100拆招")
        g.chaizhao(less_win = self.hurt_enemy, difficulty = 11)
  def __str__(self):
    return "(当骰子出目为 1/2 时，变为你的上风)"
@dataclass(repr=False)
class skill_jinzhongzhao(base_skill):
  def __post_init__(self):
    self.type = ST_MODIFY_STATE
  def __call__(self, g: game, is_greater: bool, is_chaizhao: bool):
    if is_chaizhao:
      return
    if is_greater:
      for i, val in enumerate(g.tmp_state_lst):
        if val == DISADVANTAGE:
          g.tmp_state_lst[i] = DRAW
    else:
      for i, val in enumerate(g.tmp_state_lst):
        if val == ADVANTAGE:
          g.tmp_state_lst[i] = DRAW
  def __str__(self):
    return "你的下风区间变为均势区间"
@dataclass(repr=False)
class skill_13_disadvantage_24_advantage(base_skill):
  def __post_init__(self):
    self.type = ST_ETERNAL_MODIFY_STATE
  def __call__(self, g: game, is_greater: bool, is_chaizhao: bool):
    if is_chaizhao:
      return
    if is_greater:
      g.state_lst[0], g.state_lst[1], g.state_lst[2], g.state_lst[3] = DISADVANTAGE, ADVANTAGE, DISADVANTAGE, ADVANTAGE
    else:
      g.state_lst[6], g.state_lst[7], g.state_lst[8], g.state_lst[9] = DISADVANTAGE, ADVANTAGE, DISADVANTAGE, ADVANTAGE
  def __str__(self):
    return f"13 变为 {DISADVANTAGE}，24 变为 {ADVANTAGE}"
@dataclass(repr=False)
class skill_cxx9dog_always_advantage(base_skill):
  def __post_init__(self):
    self.type = ST_MODIFY_STATE
  def __call__(self, g: game, is_greater: bool, is_chaizhao: bool):
    if is_chaizhao:
      return
    if is_greater:
      if g.last_dice_result() == 1 or g.last_dice_result() == 3:
        g.last_state = DISADVANTAGE
        g.is_state_locked = True
      elif g.last_dice_result() == 2 or g.last_dice_result() == 4:
        g.last_state = ADVANTAGE
        g.is_state_locked = True
    else:
      if g.last_dice_result() == 10 or g.last_dice_result() == 8:
        g.last_state = ADVANTAGE
        g.is_state_locked = True
      elif g.last_dice_result() == 7 or g.last_dice_result() == 9:
        g.last_state = DISADVANTAGE
        g.is_state_locked = True
  def __str__(self):
    return f"出目为 1/3 时变为 {DISADVANTAGE}，为 2/4 时变为 {ADVANTAGE}"
@dataclass(repr=False)
class skill_random_ban_skill(base_skill):
  def __post_init__(self):
    self.type = ST_EXTRA_ATK
  def __call__(self, g: game, is_greater: bool, is_chaizhao: bool):
    if is_chaizhao:
      return
    can_forbid = []
    if is_greater:
      for num, skill in enumerate(g.less_player.skills):
        if not skill.is_forbidden:
          can_forbid.append(num)
    else:
      for num, skill in enumerate(g.greater_player.skills):
        if not skill.is_forbidden:
          can_forbid.append(num)
    if len(can_forbid) > 0:
      i = can_forbid[random.randint(0, len(can_forbid) - 1)]
      if is_greater:
        forbid_skill(g.less_player.skills[i])
      else:
        forbid_skill(g.greater_player.skills[i])
  def __str__(self):
    return "回合末随机封禁对方一个特质"
@dataclass(repr=False)
class skill_extra_honglianhuamie(base_skill):
  def __post_init__(self):
    self.type = ST_GROUP
    self.sub_skills = [skill_plus(num=1), skill_random_ban_skill()]
def turn_one_range(lst: list, state_from: SkillType, state_to: SkillType):
  choice = None
  for i, state in enumerate(lst):
    if state == state_from:
      choice = i
  if choice is not None:
    lst[choice] = state_to
@dataclass(repr=False)
class skill_disadvantage_draw_to_advantage(base_skill):
  def __post_init__(self):
    self.type = ST_EXTRA_ATK
  def __call__(self, g: game, is_greater: bool, is_chaizhao: bool):
    if is_chaizhao:
      return
    if is_greater:
      if g.last_state == DISADVANTAGE:
        turn_one_range(g.state_lst, DRAW, ADVANTAGE)
    else:
      if g.last_state == ADVANTAGE:
        turn_one_range(g.state_lst, DRAW, DISADVANTAGE)
  def __str__(self):
    return "当结果为下风时，将一个均势区间变为上风"
@dataclass(repr=False)
class skill_advantage_disadvantage_to_draw(base_skill):
  def __post_init__(self):
    self.type = ST_EXTRA_ATK
  def __call__(self, g: game, is_greater: bool, is_chaizhao: bool):
    if is_chaizhao:
      return
    if is_greater:
      if g.last_state == ADVANTAGE:
        turn_one_range(g.state_lst, DISADVANTAGE, DRAW)
    else:
      if g.last_state == DISADVANTAGE:
        turn_one_range(g.state_lst, ADVANTAGE, DRAW)
  def __str__(self):
    return "当结果为上风时，将一个下风区间变为均势"
@dataclass(repr=False)
class skill_wgu_attack(base_skill):
  def __post_init__(self):
    self.type = ST_GROUP
    self.sub_skills = [skill_advantage_disadvantage_to_draw(),
                       skill_disadvantage_draw_to_advantage()]
@dataclass(repr=False)
class skill_average_to_win(base_skill):
  def __post_init__(self):
    self.type = ST_ETERNAL_MODIFY_STATE
  def __call__(self, g: game, is_greater: bool, is_chaizhao: bool):
    if is_chaizhao:
      return
    if is_greater:
      for _ in range(10):
        turn_one_range(g.state_lst, DRAW, WIN)
    else:
      for _ in range(10):
        turn_one_range(g.state_lst, DRAW, LOSS)
  def __str__(self):
    return "你的均势区间变为获胜"
@dataclass(repr=False)
class skill_ytj_weixiwu(base_skill):
  usable_times:int = 1
  def __post_init__(self):
    self.type = ST_EXTRA_ATK
  def __call__(self, g: game, is_greater: bool, is_chaizhao: bool):
    if is_chaizhao or self.usable_times == 0:
      return
    if is_greater:
      if g.last_state == LOSS or g.last_state == DISADVANTAGE:
        self.usable_times -= 1
        g.last_state = DRAW
    else:
      if g.last_state == WIN or g.last_state == ADVANTAGE:
        self.usable_times -= 1
        g.last_state = DRAW
  def __str__(self):
    return "你免除第一次伤害"
@dataclass(repr=False)
class skill_plus_half(base_skill):
  def __post_init__(self):
    self.type = ST_ADD
  def __call__(self, g: game, is_greater: bool, is_chaizhao: bool):
    if is_chaizhao:
      pass
    if is_greater:
      g.add += random.randint(0, 1)
    else:
      g.add -= random.randint(0, 1)
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
@dataclass(repr=False)
class skill_guoshiwushuang(base_skill):
  used: bool = False
  def __post_init__(self):
    self.type = ST_GET_NUM
  def __call__(self, g: game, is_greater: bool, is_chaizhao: bool):
    if is_chaizhao or self.used:
      return
    if is_greater and two_tail_sum(g.dice_history[-1]) == 1:
      self.used = True
      return 10
    elif not is_greater and two_tail_sum(g.dice_history[-1]) == 10:
      self.used = True
      return 1
@dataclass(repr=False)
class skill_advantage_plus2(base_skill):
  def __post_init__(self):
    self.type = ST_EXTRA_ATK
  def __call__(self, g: game, is_greater: bool, is_chaizhao: bool):
    if is_chaizhao:
      return
    if is_greater:
      if g.last_state == ADVANTAGE:
        g.eternal_add += 1
    else:
      if g.last_state == DISADVANTAGE:
        g.eternal_add -= 1
  def __str__(self):
    return "上风时额外获得 +1"
@dataclass(repr=False)
class skill_draw_plus1(base_skill):
  def __post_init__(self):
    self.type = ST_EXTRA_ATK
  def __call__(self, g: game, is_greater: bool, is_chaizhao: bool):
    if is_chaizhao:
      return
    if is_greater:
      if g.last_state == DRAW:
        g.eternal_add += 1
    else:
      if g.last_state == DRAW:
        g.eternal_add -= 1
  def __str__(self):
    return "均势时额外获得 +1"
@dataclass(repr=False)
class skill_buzhierding(base_skill):
  def __post_init__(self):
    self.type = ST_ADD
  def __call__(self, g: game, is_greater: bool, is_chaizhao: bool):
    if is_chaizhao:
      return
    if g.turn % 2 == 0:
      add = 3 if is_greater else -3
      g.add += add
    else:
      add = 1 if is_greater else -1
      g.eternal_add += add
  def __str__(self):
    return "(奇数回合获得 +3，偶数回合永久 +1)"
@dataclass(repr=False)
class skill_haidilaoyue_enhanced(base_skill):
  def __post_init__(self):
    self.type = ST_GET_NUM
  def __call__(self, g: game, is_greater: bool, is_chaizhao: bool):
    if is_chaizhao or self.used:
      return
    if is_greater and two_tail_sum(g.dice_history[-1]) == 1:
      return 10
    elif not is_greater and two_tail_sum(g.dice_history[-1]) == 10:
      return 1
  def __str__(self):
    return "(战斗时，出 1 视为 0)"
@dataclass(repr=False)
class skill_xingyunwuchang(base_skill):
  def __post_init__(self):
    self.type = ST_ETERNAL_MODIFY_STATE
  def __call__(self, g: game, is_greater: bool, is_chaizhao: bool):
    if is_chaizhao:
      return
    i = random.randint(0, len(g.state_lst) - 1)
    choice = WIN if is_greater else LOSS
    g.state_lst[i] = choice
  def __str__(self):
    return "(每回合变化一个随机区间为获胜)"
@dataclass(repr=False)
class skill_xingyunwuchang2(base_skill):
  def __post_init__(self):
    self.type = ST_ETERNAL_MODIFY_STATE
  def __call__(self, g: game, is_greater: bool, is_chaizhao: bool):
    if is_chaizhao:
      return
    choice = WIN if is_greater else LOSS
    id = None
    for i, state in enumerate(g.state_lst):
      if state != choice:
        id = i
        break
    if id is not None:
      g.state_lst[id] = choice
  def __str__(self):
    return "(每回合变化一个最小非胜区间为获胜)"