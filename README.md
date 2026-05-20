# ytj-system DSL Battle Simulator

This is a simple DSL simulator for **ytj-system battle**, an RPG-style random battle game discussed on [X Island / nmbxd1](https://www.nmbxd1.com/Forum).

More discussion about the game is welcomed here:

[https://www.nmbxd1.com/t/61234529](https://www.nmbxd1.com/t/61234529)

The simulator is written in Python and is designed for quickly testing skill designs through Monte Carlo simulation.

---

## Software Requirement

To run this simulator, you need:

```bash
Python >= 3.11.9
```

---

## Execution

First, modify `main.py` with the players and skills you want to test.

Then run:

```bash
python3 main.py
```

A minimal example:

```python
from skill import *

p1 = player([
  rcall_plus(num=1),
])

p2 = player([
  rcall_plus(num=0),
])

g = game(
  p1,
  p2,
  base_dice(),
  {"advantage": "advantage", "disadvantage": "disadvantage"}
)

simulate_game_auto_batch(g, N=100000)
```

---

# Introduction to ytj-system

ytj-system is a random battle game based on a 10-sided dice. Since its core rules are discrete and probabilistic, it is easy to simulate by computer.

A game has two players:

* the **greater player**, abbreviated as `G`
* the **less player**, abbreviated as `L`

Most states are described from the greater player's perspective. For example, `WIN` means the greater player wins, while `LOSS` means the less player wins.

---

## Main Loop

The game runs in turns:

```text
roll dice -> modify result -> get battle state -> end game or repeat
```

Once a player rolls the dice, the game gets a number in `[1, 10]`. This number is used as an index into the current state list.

The usual state list is:

```text
1       LOSS
2,3,4   DISADVANTAGE
5,6     DRAW
7,8,9   ADVANTAGE
10      WIN
```

There are two terminal states:

* `WIN`: the greater player wins immediately
* `LOSS`: the less player wins immediately

There are also three non-terminal states:

* `ADVANTAGE`
* `DRAW`
* `DISADVANTAGE`

If the result is `ADVANTAGE`, the game counter `eternal_add` increases by `1`. If the result is `DISADVANTAGE`, `eternal_add` decreases by `1`. If the result is `DRAW`, nothing changes.

In other words, you may imagine that there is a counter on the table:

```text
ADVANTAGE     -> counter += 1
DRAW          -> counter += 0
DISADVANTAGE  -> counter -= 1
```

On the next turn, the real result index is:

```text
dice result + counter
```

---

## Countermove / Chai Zhao

Countermove, also called **Chai Zhao**, is a special way to win.

If two `ADVANTAGE` or two `DISADVANTAGE` states appear in a row, the game performs an extra countermove check.

From the greater player's perspective:

```text
if countermove result > 5:
  greater player succeeds
else:
  less player succeeds
```

If there are two `ADVANTAGE` states in a row, the less player is considered the flawed one. If the flawed one fails the countermove, they lose immediately.

If there are two `DISADVANTAGE` states in a row, the greater player is considered the flawed one. If the flawed one fails the countermove, they lose immediately.

---

## Custom Dice: Tail

On X Island, every message has an ID number. Players often use the last digit of the message ID as a 10-sided dice. This is called a **tail**.

A common custom is to use the sum of two tails modulo 10 as the dice result.

The two tails can also be used as independent random sources for skill design. For example, instead of saying:

```text
a random number from 1 to 5
```

one may write:

```text
floor(first tail / 2)
```

In the simulator, tails can be accessed with:

```python
Tail(0)  # first tail
Tail(1)  # second tail
```

---

# DSL Overview

This simulator provides a small DSL for writing skills. A skill is usually built from two parts:

1. **Expr**: a value that can be evaluated during the game, such as `Turn()`, `Tail(0)`, `LastValue()`, or `TriggerCounter("skill_name")`.
2. **rcall skill**: an effect that changes the game, such as `rcall_plus`, `rcall_range_change`, or `rcall_eternal_plus`.

For example:

```python
rcall_plus(num=1)
```

means:

```text
this player gets +1 to the current result
```

A more dynamic skill:

```python
rcall_plus(num=Tail(0) // 2)
```

means:

```text
this player gets floor(first_tail / 2) as a bonus
```

---

# Basic Imports

You can either import everything:

```python
from skill import *
```

or import only the API you need.

A recommended explicit import order is:

```python
import skill

from skill import game, player, base_dice, simulate_game_auto_batch
from skill import BEGIN, LOSS, DISADVANTAGE, DRAW, ADVANTAGE, WIN

# Game data expressions
from skill import LastDiceResult, LastDirectSum, LastRange, LastValue
from skill import Turn, Tail
from skill import RangeAt, TempRangeAt, FindRange, FindTempRange
from skill import GameAddValue, GameDiceHistory, GameDiceResultHistory
from skill import GameEternalAddValue, GameStateHistory
from skill import RandomFloat, RandomUniform, RandomDict
from skill import And, Or, Not
from skill import CounterValue, TriggerCounter
from skill import CounterAdd, CounterSet

# Skill constructors
from skill import rcall_plus, rcall_count_plus, rcall_eternal_plus
from skill import rcall_last_range_change, rcall_range_change, rcall_temp_range_change
from skill import rcall_num_view_as
```

---

# Core Objects

## `player`

A player is created from a list of skills:

```python
p = player([
  rcall_plus(num=1),
  rcall_plus(num=Tail(0) // 2),
])
```

The first player passed to `game(...)` is the greater player. The second player is the less player.

```python
g = game(greater_player, less_player, dice, mode_method)
```

---

## `game`

A game stores the complete state of one battle, including:

* current state list
* temporary state list
* dice history
* result history
* current `eternal_add`
* turn number
* custom counters
* player skills

Normally, users do not need to manipulate `game` directly. Skills and expressions read or modify it internally.

Example:

```python
g = game(
  p1,
  p2,
  base_dice(),
  {"advantage": "advantage", "disadvantage": "disadvantage"}
)
```

---

## `base_dice`

`base_dice()` is the default uniform 10-sided dice:

```python
dice = base_dice()
```

It returns an integer from `1` to `10`.

---

# Battle States

The simulator defines the following battle states:

```python
BEGIN
LOSS
DISADVANTAGE
DRAW
ADVANTAGE
WIN
```

Their usual meanings are:

| State          | Meaning                                               |
| -------------- | ----------------------------------------------------- |
| `BEGIN`        | special sentinel state before the first real turn     |
| `LOSS`         | greater player loses immediately                      |
| `DISADVANTAGE` | greater player is in disadvantage; `eternal_add -= 1` |
| `DRAW`         | no change                                             |
| `ADVANTAGE`    | greater player is in advantage; `eternal_add += 1`    |
| `WIN`          | greater player wins immediately                       |

---

# Expression System

Most DSL parameters accept either a normal Python value or an `Expr`.

For example, `num` in `rcall_plus(num=...)` can be:

```python
1
Tail(0)
Turn() + 1
TriggerCounter("my_skill")
(LastValue() >= 5).ifelse(2, 0)
```

Expressions can be combined with ordinary arithmetic and comparisons:

```python
Tail(0) + 1
Tail(0) // 2
Turn() % 3
LastValue() >= 7
LastRange().isin(ADVANTAGE, WIN)
```

Conditional logic is written with `.ifelse(...)`:

```python
(LastValue() >= 7).ifelse(2, 0)
```

This means:

```text
if LastValue() >= 7:
  return 2
else:
  return 0
```

---

# Game Data Expressions

## `Turn()`

Returns the current turn number. It starts from `0`.

Example:

```python
rcall_plus(num=Turn())
```

This gives `+0` on the first turn, `+1` on the second turn, and so on.

---

## `Tail(i)`

Returns the `i`-th tail of the current dice roll.

```python
Tail(0)  # first tail
Tail(1)  # second tail
```

Example:

```python
rcall_plus(num=Tail(0) // 2)
```

---

## `LastDiceResult()`

Returns the last dice result after dice calculation.

Example:

```python
rcall_plus(
  num=(LastDiceResult() >= 7).ifelse(1, 0)
)
```

---

## `LastDirectSum()`

Returns the direct sum of the two tails before modulo conversion.

Example:

```python
rcall_plus(num=LastDirectSum() // 5)
```

---

## `LastValue()`

Returns the current final value after dice, temporary bonuses, and permanent battle counter are applied.

Example:

```python
rcall_plus(
  num=(LastValue() <= 4).ifelse(2, 0)
)
```

---

## `LastRange()`

Returns the current result range, such as `DRAW` or `ADVANTAGE`.

Example:

```python
rcall_plus(
  num=LastRange().isin(DISADVANTAGE, LOSS).ifelse(1, 0)
)
```

---

# Range Expressions

## `RangeAt(i)`

Reads the permanent state list at index `i`.

```python
RangeAt(0)  # usually LOSS
RangeAt(4)  # usually DRAW
```

---

## `TempRangeAt(i)`

Reads the temporary state list at index `i`.

Temporary range changes only affect the current turn.

---

## `FindRange(state, find_order=0)`

Finds a state in the permanent state list.

```python
FindRange(DRAW)
```

finds the first `DRAW` from left to right.

```python
FindRange(DISADVANTAGE, find_order=1)
```

finds the last `DISADVANTAGE` from right to left.

This is useful for skills that modify a boundary of the result table.

Example:

```python
rcall_range_change(
  range_id=FindRange(DISADVANTAGE, find_order=1),
  arg=1
)
```

This changes the last `DISADVANTAGE` into a better state.

---

## `FindTempRange(state, find_order=0)`

Like `FindRange`, but searches in the temporary state list.

Use this with `rcall_temp_range_change`.

---

# Random Expressions

## `RandomFloat()`

Returns a random float in `[0, 1)`.

Example:

```python
rcall_plus(
  num=(RandomFloat() < 0.5).ifelse(1, 0)
)
```

---

## `RandomUniform(lower, upper)`

Returns a random integer in `[lower, upper]`.

Example:

```python
rcall_plus(num=RandomUniform(1, 3))
```

---

## `RandomDict({...})`

Returns a weighted random value.

Example:

```python
rcall_plus(
  num=RandomDict({
    0.5: 0,
    0.3: 1,
    0.2: 2,
  })
)
```

The probabilities should sum to `1.0`.

---

# Logic Expressions

You can use Python operators:

```python
LastValue() >= 7
Turn() < 3
Tail(0).eq(10)
```

Since Python does not allow overloading `and`, `or`, and `not` in the desired way, use either:

```python
And(a, b)
Or(a, b)
Not(a)
```

or the overloaded bitwise operators:

```python
(a & b)
(a | b)
(~a)
```

Example:

```python
rcall_plus(
  valid_when=(Turn() < 3) & (LastValue() >= 5),
  num=1
)
```

---

# Counter System

The simulator has a general counter system stored in `game.game_counter`.

Counters are useful for writing skills such as:

* trigger only a limited number of times
* accumulate a value across turns
* reset a value after a condition is met
* count how many times a named skill has triggered

---

## `CounterValue(name)`

Reads a custom counter.

Example:

```python
CounterValue("acc_val")
```

You can use it inside expressions:

```python
rcall_plus(
  num=(CounterValue("acc_val") >= 10).ifelse(2, 0)
)
```

---

## `CounterAdd(name=..., value=...)`

Adds a value to a counter.

Example:

```python
CounterAdd(name="acc_val", value=Tail(1))
```

Important: prefer keyword arguments.

```python
# Recommended
CounterAdd(name="acc_val", value=Tail(1))

# Avoid this, because positional fields may not mean what you expect
CounterAdd("acc_val", Tail(1))
```

---

## `CounterSet(name=..., value=...)`

Sets a counter to a value.

Example:

```python
CounterSet(name="acc_val", value=0)
```

---

## `TriggerCounter(skill_name)`

Reads how many times a named skill has triggered.

For a skill to be counted, give it a `skill_name`:

```python
rcall_plus(
  skill_name="test_skill",
  num=1
)
```

Then another expression can read its trigger count:

```python
TriggerCounter("test_skill")
```

Example: a skill that only works twice:

```python
rcall_plus(
  skill_name="test_skill",
  valid_when=TriggerCounter("test_skill") < 2,
  num=1
)
```

Example: a skill that still triggers after two times, but gives `0` bonus later:

```python
rcall_plus(
  skill_name="test_skill",
  num=(TriggerCounter("test_skill") <= 2).ifelse(1, 0)
)
```

---

# Skill System

Most DSL skills are subclasses of `r_skill`.

A skill can have several common parameters:

```python
skill_name: str | None
before_check: list[CounterAction]
on_trigger: list[CounterAction]
on_work_after: list[CounterAction]
valid_when: Expr | bool
```

The execution order is:

```text
before_check
    ↓
check valid_when
    ↓
automatically record trigger count if skill_name is not None
    ↓
on_trigger
    ↓
work
    ↓
on_work_after
```

This order is important.

For example, if you want to accumulate a counter before testing whether a skill should trigger, put the accumulation in `before_check`.

If you want to clear a counter after the skill effect is applied, put the reset in `on_work_after`.

---

## `valid_when`

`valid_when` controls whether a skill triggers.

By default, most rcall skills only work in normal battle turns, not in countermove turns.

Example:

```python
rcall_plus(
  valid_when=Turn() < 3,
  num=1
)
```

This skill gives `+1` only before turn 3.

Example:

```python
rcall_plus(
  valid_when=LastValue() >= 7,
  num=2
)
```

This skill gives `+2` only when the current value is at least 7.

---

# Skill Constructors

## `rcall_plus(num=...)`

Adds a temporary bonus to the current result.

For the greater player, positive `num` means a better result. For the less player, the sign is automatically reversed.

```python
rcall_plus(num=1)
```

means:

```text
this player gets +1 this turn
```

Examples:

```python
# Always +1
rcall_plus(num=1)

# +Tail(0)
rcall_plus(num=Tail(0))

# +2 for the 1st turn, +1 for the 2nd turn and +0 otherwise
rcall_plus(num=[2,1])

# +2 only when LastValue >= 7
rcall_plus(
  num=(LastValue() >= 7).ifelse(2, 0)
)
```

---

## `rcall_count_plus(num=...)`

Accumulates an internal count and adds the accumulated value to the current result.

Example:

```python
rcall_count_plus(num=1)
```

This gives:

```text
turn 1: +1
turn 2: +2
turn 3: +3
...
```

Note: for more complex accumulation logic, prefer the general counter system with `CounterValue`, `CounterAdd`, and `CounterSet`.

---

## `rcall_eternal_plus(num=...)`

Adds to the permanent battle counter `eternal_add`.

Example:

```python
rcall_eternal_plus(num=1)
```

This gives the player a permanent `+1` to future results.

Example with custom counter:

```python
rcall_eternal_plus(
  skill_name="acc_plus",
  before_check=[
    CounterAdd(name="acc_val", value=Tail(1))
  ],
  valid_when=CounterValue("acc_val") >= 10,
  num=1,
  on_work_after=[
    CounterAdd(name="acc_val", value=-10)
  ]
)
```

This means:

```text
before checking the skill, add Tail(1) to acc_val
if acc_val >= 10, trigger the skill
when triggered, gain permanent +1
after triggering, reduce acc_val by 10
```

---

## `rcall_last_range_change(arg=..., source=...)`

Modifies the current result range.

If `arg` is an integer, it shifts the range by that many levels.

```python
rcall_last_range_change(arg=1)
```

means:

```text
make the current result one level better for this player
```

For example:

```text
DISADVANTAGE -> DRAW
DRAW -> ADVANTAGE
ADVANTAGE -> WIN
```

If `arg` is a battle state, the result is directly viewed as that state.

```python
rcall_last_range_change(arg=ADVANTAGE)
```

means:

```text
view the current result as ADVANTAGE
```

---

## `rcall_range_change(range_id=..., arg=...)`

Permanently modifies the state list.

Example:

```python
rcall_range_change(
  range_id=FindRange(DISADVANTAGE, find_order=1),
  arg=1
)
```

This finds the last `DISADVANTAGE` in the permanent state list and improves it by one level.

This is useful for skills similar to:

```text
change one disadvantage range into draw
```

---

## `rcall_temp_range_change(range_id=..., arg=...)`

Temporarily modifies the state list for the current turn only.

Example:

```python
rcall_temp_range_change(
  range_id=FindTempRange(DRAW),
  arg=1
)
```

This finds the first `DRAW` in the temporary state list and improves it by one level for this turn.

---

## `rcall_num_view_as(num=...)`

Views the dice result as a specific number.

Example:

```python
rcall_num_view_as(num=10)
```

This makes the dice result count as `10`.

Note: this API is less recommended now, because many similar effects can be expressed with `rcall_plus` or range modification skills.

## `rcall_armor`

A special mechanism called "armor". To turn LOSS into DRAW spending armor, one need 1 armor for a 1 LOSS, 2 armor for a 0 LOSS, 3 armor for a -1 LOSS and so on.

Example:

```python
rcall_armor(armor_name="abc", value=2, armor_effect=DRAW)
```

It create a skill name that is "armor:abc" with 2 armor. It will turn LOSS into DRAW if allowed.

---

# Complete Examples

## Example 1: Always +1

```python
from skill import *

p1 = player([
  rcall_plus(num=1),
])

p2 = player([
  rcall_plus(num=0),
])

g = game(p1, p2, base_dice(), {
  "advantage": "advantage",
  "disadvantage": "disadvantage",
})

simulate_game_auto_batch(g, N=100000)
```

---

## Example 2: First three turns get +1

```python
p1 = player([
  rcall_plus(
    valid_when=Turn() < 3,
    num=1
  )
])
```

---

## Example 3: A skill that triggers only twice

```python
p1 = player([
  rcall_plus(
    skill_name="limited_plus",
    valid_when=TriggerCounter("limited_plus") < 2,
    num=1
  )
])
```

This gives `+1` only for the first two successful triggers.

---

## Example 4: Accumulate a custom counter

```python
p1 = player([
  rcall_eternal_plus(
    skill_name="acc_plus",
    before_check=[
      CounterAdd(name="acc_val", value=Tail(1))
    ],
    valid_when=CounterValue("acc_val") >= 10,
    num=1,
    on_work_after=[
      CounterAdd(name="acc_val", value=-10)
    ]
  )
])
```

This skill accumulates `Tail(1)` every time it is checked. When the counter reaches at least `10`, it gives permanent `+1` and then reduces the counter by `10`.

---

## Example 5: Reproduce a boundary-changing skill

Suppose you want to change the last `DISADVANTAGE` into `DRAW` on turn 0.

```python
p1 = player([
  rcall_range_change(
    valid_when=Turn().eq(0),
    range_id=FindRange(DISADVANTAGE, find_order=1),
    arg=1
  )
])
```

The usual state list is:

```text
LOSS, DISADVANTAGE, DISADVANTAGE, DISADVANTAGE, DRAW, DRAW, ADVANTAGE, ADVANTAGE, ADVANTAGE, WIN
```

After this skill, it becomes:

```text
LOSS, DISADVANTAGE, DISADVANTAGE, DRAW, DRAW, DRAW, ADVANTAGE, ADVANTAGE, ADVANTAGE, WIN
```

---

# Notes and Pitfalls

## Prefer keyword arguments for counter actions

Because `CounterAdd` and `CounterSet` inherit fields from `CounterAction`, positional arguments may be confusing.

Prefer:

```python
CounterAdd(name="acc_val", value=Tail(1))
CounterSet(name="acc_val", value=0)
```

Avoid:

```python
CounterAdd("acc_val", Tail(1))
```

---

## Temporary bonus vs permanent bonus

Use `rcall_plus` for current-turn bonus:

```python
rcall_plus(num=1)
```

Use `rcall_eternal_plus` for permanent battle counter changes:

```python
rcall_eternal_plus(num=1)
```

---

## Permanent range change vs temporary range change

Use `rcall_range_change` to modify the permanent state list.

Use `rcall_temp_range_change` to modify only the temporary state list for the current turn.

---

## Trigger count means successful trigger

`TriggerCounter("name")` counts successful triggers, not merely checks.

A skill triggers only when `valid_when` passes.

---

## Order matters

For every `r_skill`, the order is:

```text
before_check -> valid_when -> trigger count -> on_trigger -> work -> on_work_after
```

Use `before_check` if the counter update should happen before testing the condition.

Use `on_work_after` if the update should happen after the skill effect.

---

# Recommended Project Structure

A simple project layout can be:

```text
ytj-simulator/
├── README.md
├── main.py
├── skill.py
└── .gitignore
```

`skill.py` contains the simulator and DSL implementation.

`main.py` contains the experiment you want to run.

---