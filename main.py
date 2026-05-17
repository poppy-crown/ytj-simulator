import skill

from skill import game, player, base_dice, simulate_game_auto_batch, simulate
# 游戏，玩家，均匀骰子，模拟主函数
from skill import BEGIN, LOSS, DISADVANTAGE, DRAW, ADVANTAGE, WIN
# 开局(这是一个特殊状态，正常来说只有“第一回合的上一回合”是这个状态)，战败，下风，均势，上风，战胜
from skill import IsChaizhao, NotChaizhao
# 是否是拆招
from skill import SeqExpr, Bounce, StayTail, Once, OnceAsTurn, Loop

"""游戏数据相关 API"""
from skill import LastDiceResult, LastDirectSum, LastRange, LastValue
# Last 其实是这回合或上回合的数据，取决于技能发动的时机
from skill import Turn, Tail
# 回合数，尾数(都从 0 开始)
from skill import RangeAt, TempRangeAt, FindRange, FindTempRange
# 区间相关的 API
from skill import GameAddValue, GameDiceHistory, GameDiceResultHistory, GameEternalAddValue, GameStateHistory
# game 相关数据的 API(用得比较少)
from skill import GameEternalSkillPlus, EternalSkillPlusAt
# 技能永久加值(总和)，技能永久加值(单个)
from skill import RandomFloat, RandomUniform, RandomDict
# 0-1 随机实数，均匀随机整数，带权随机数
from skill import And, Or, Not
# 逻辑与或非
from skill import CounterValue, TriggerCounter
# 统计任意变量，统计技能触发次数
from skill import CounterAdd, CounterSet
# 对变量加，对变量赋值

"""技能相关 API"""
from skill import rcall_plus, rcall_count_plus, rcall_eternal_plus
# 加值，永久加值
from skill import rcall_last_range_change, rcall_range_change, rcall_temp_range_change
# 修改本轮结果，永久修改区间，仅在本轮修改区间
from skill import rcall_num_view_as
# 值视为，这个 API 已经不再维护，因为新的 plus 可以覆盖其功能

if __name__ == "__main__":
  p1 = player([
              rcall_eternal_plus(
                skill_name="aa",
                valid_when=EternalSkillPlusAt(skill_name="aa")<2,
                num=1
              )
            ])
  p2 = player([
              rcall_plus(num=2),
            ])
  g = game(p1, p2, base_dice(),
           {"advantage":"advantage", "disadvantage":"disadvantage"}
           )
  simulate_game_auto_batch(
    generator=g,
    confidence_level=0.99,
    deviation=0.003,
    worker_num=6
  )