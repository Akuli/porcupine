"""Tetris game."""
# TODO: make pause feature discoverable to users
# FIXME: "game over" text doesn't show up very well on top of white squares

import functools
import itertools
import random
import tkinter
from typing import Dict, Iterator, List, Optional, Tuple

from porcupine import get_tab_manager, menubar, tabs, utils

WIDTH = 10
HEIGHT = 20
SCALE = 20     # each square is 20x20 pixels

Point = Tuple[int, int]
ShapeLetter = str

# the shapes are lists of (x, y) coordinates where (0, 0) is the point
# that the shape rotates around and top center of the game when the
# shape is added to it
# y is like in math, so more y means higher
SHAPES: Dict[ShapeLetter, List[Point]] = {
    'I': [(0, 2),
          (0, 1),
          (0, 0),
          (0, -1)],
    'O': [(-1, 0), (0, 0),
          (-1, 1), (0, 1)],
    'T': [(-1, 0), (0, 0), (1, 0),
                   (0, -1)],
    'L': [(0, 1),
          (0, 0),
          (0, -1), (1, -1)],
    'J': [
            (0, 1),            # noqa
            (0, 0),
  (-1, -1), (0, -1)],          # noqa
    'S': [
            (0, 1), (1, 1),    # noqa
   (-1, 0), (0, 0)],           # noqa
    'Z': [(-1, 1), (0, 1),
                   (0, 0), (1, 0)],
}


class Block:
    """The block that is currently moving down the game.

    Other blocks end up in Game.frozen_squares.
    """

    def __init__(self, game: 'Game', shape_letter: ShapeLetter) -> None:
        self._game = game
        self.shape_letter = shape_letter
        self.shape = SHAPES[shape_letter].copy()
        self.x = WIDTH // 2
        self.y = HEIGHT

    # for debugging
    def __repr__(self) -> str:
        return f'<{self.shape_letter}-shaped {type(self).__name__} at ({self.x}, {self.y})>'

    def get_coords(self) -> Iterator[Point]:
        for shapex, shapey in self.shape:
            yield (self.x + shapex, self.y + shapey)

    def bumps(self, x: int, y: int) -> bool:
        return (x not in range(WIDTH) or y < 0 or (x, y) in self._game.frozen_squares)

    def _move(self, deltax: int, deltay: int) -> bool:
        for x, y in self.get_coords():
            if self.bumps(x + deltax, y + deltay):
                return False

        self.x += deltax
        self.y += deltay
        return True

    move_left = functools.partialmethod(_move, -1, 0)
    move_right = functools.partialmethod(_move, +1, 0)
    move_down = functools.partialmethod(_move, 0, -1)

    def move_down_all_the_way(self) -> None:
        while self.move_down():
            pass

    def rotate(self) -> bool:
        new_shape: List[Point] = []
        for old_x, old_y in self.shape:
            x, y = -old_y, old_x
            if self.bumps(self.x + x, self.y + y):
                return False
            new_shape.append((x, y))

        self.shape[:] = new_shape
        return True


class NonRotatingBlock(Block):

    def rotate(self) -> bool:
        return False


class TwoRotationsBlock(Block):

    _rotations: Optional[Iterator[List[Point]]] = None

    def rotate(self) -> bool:
        if self._rotations is None:
            # running this for the first time
            before = self.shape.copy()
            if not super().rotate():
                # bumping into a wall, maybe we can do something next time
                return False
            after = self.shape.copy()
            self._rotations = itertools.cycle([before, after])
            return True

        else:
            new_shape = next(self._rotations)
            for x, y in new_shape:
                if self.bumps(self.x + x, self.y + y):
                    # restore self._rotations back to the state before
                    # calling this method to make things look like
                    # nothing happened
                    next(self._rotations)
                    return False
            self.shape = new_shape
            return True


class Game:

    moving_block: Block

    def __init__(self) -> None:
        self.frozen_squares: Dict[Point, str] = {}
        self.score = 0        # each new block increments score
        self.add_block()      # creates self.moving_block
        self.paused = False   # only used outside this class definition

    @property
    def level(self) -> int:
        # levels start at 1
        return self.score//30 + 1    # noqa

    @property
    def delay(self) -> int:
        """The waiting time between do_something() calls as milliseconds."""
        return 300 - (30 * self.level)

    def add_block(self) -> None:
        letter = random.choice(list(SHAPES.keys()))
        if letter == 'O':
            self.moving_block = NonRotatingBlock(self, letter)
        elif letter in {'I', 'S', 'Z'}:
            self.moving_block = TwoRotationsBlock(self, letter)
        else:
            self.moving_block = Block(self, letter)

    def shape_at(self, x: int, y: int) -> Optional[ShapeLetter]:
        try:
            return self.frozen_squares[(x, y)]
        except KeyError:
            assert self.moving_block is not None
            if (x, y) in self.moving_block.get_coords():
                return self.moving_block.shape_letter
            return None

    def freeze_moving_block(self) -> None:
        for x, y in self.moving_block.get_coords():
            self.frozen_squares[(x, y)] = self.moving_block.shape_letter

    def delete_full_lines(self) -> None:
        # this is much easier with a nested list
        lines = []
        for y in range(HEIGHT):
            line = [self.frozen_squares.pop((x, y), None)
                    for x in range(WIDTH)]
            if None in line:
                # it's not full, we can keep it
                lines.append(line)

        for y, line in enumerate(lines):
            for x, value in enumerate(line):
                if value is not None:
                    self.frozen_squares[(x, y)] = value

    def do_something(self) -> None:
        if self.moving_block.move_down():
            return

        self.freeze_moving_block()
        self.add_block()
        self.delete_full_lines()
        self.score += 1

    def game_over(self) -> bool:
        """Return True if the game is over."""
        return any((x, HEIGHT) in self.frozen_squares for x in range(WIDTH))


COLORS: Dict[ShapeLetter, str] = {
    'I': 'red',
    'O': 'blue',
    'T': 'yellow',
    'L': 'magenta',
    'J': 'white',
    'S': 'green',
    'Z': 'cyan',
}


class TetrisTab(tabs.Tab):

    def __init__(self, manager: tabs.TabManager) -> None:
        super().__init__(manager)
        self.title_choices = ["Tetris"]

        # the takefocus thing is important, it's hard to bind the keys
        # correctly without it
        self._canvas = tkinter.Canvas(
            self, width=WIDTH*SCALE, height=HEIGHT*SCALE,
            relief='ridge', bg='black', takefocus=True)
        self._canvas.pack()

        # this also requires binding on the tab when the tab is detached
        for key in ['<W>', '<w>', '<A>', '<a>', '<S>', '<s>', '<D>', '<d>',
                    '<Left>', '<Right>', '<Up>', '<Down>', '<Return>',
                    '<space>', '<F2>', '<P>', '<p>']:
            self._canvas.bind(key, self._on_key, add=True)
            self.bind(key, self._on_key, add=True)

        self._canvas_content = {}
        for x in range(WIDTH):
            for y in range(HEIGHT):
                left = x * SCALE
                bottom = (HEIGHT - y) * SCALE
                self._canvas_content[(x, y)] = self._canvas.create_rectangle(
                    left, bottom - SCALE, left + SCALE, bottom,
                    outline='black', fill='black')

        self._timeout_id: Optional[str] = None
        self._game_over_id: Optional[int] = None

        # yes, this needs force for some reason
        self.bind('<<TabSelected>>', (lambda event: self._canvas.focus_force()), add=True)

    def _on_key(self, event: 'tkinter.Event[tkinter.Misc]') -> utils.BreakOrNone:
        control_flag = 0x4
        assert isinstance(event.state, int)
        if event.state & control_flag:
            return None

        if event.keysym in {'A', 'a', 'Left'}:
            self._game.moving_block.move_left()
        elif event.keysym in {'D', 'd', 'Right'}:
            self._game.moving_block.move_right()
        elif event.keysym in {'W', 'w', 'Return', 'Up'}:
            self._game.moving_block.rotate()
        elif event.keysym in {'S', 's', 'space', 'Down'}:
            self._game.moving_block.move_down_all_the_way()
        elif event.keysym in {'P', 'p'}:
            if not self._game.game_over():
                self._game.paused = (not self._game.paused)
        elif event.keysym == 'F2':
            self.new_game()
        else:
            raise ValueError("unknown keysym %r" % event.keysym)

        self._refresh()
        return 'break'

    def _refresh(self) -> None:
        for (x, y), item_id in self._canvas_content.items():
            shape = self._game.shape_at(x, y)
            if shape is None:
                color = self._canvas.cget('bg')
            else:
                color = COLORS[shape]
            self._canvas.itemconfig(item_id, fill=color)

        self.status = "Score %d, level %d" % (
            self._game.score, self._game.level)

    def new_game(self) -> None:
        if self._timeout_id is not None:
            self.after_cancel(self._timeout_id)
        if self._game_over_id is not None:
            self._canvas.delete(self._game_over_id)
            self._game_over_id = None

        self._game = Game()
        self._refresh()
        self._on_timeout()

    def _on_timeout(self) -> None:
        if self._game.paused:
            self._timeout_id = self._canvas.after(
                self._game.delay, self._on_timeout)
            return

        self._game.do_something()
        self._refresh()

        if self._game.game_over():
            centerx = int(self._canvas.cget('width')) // 2
            centery = int(self._canvas.cget('height')) // 3
            self._game_over_id = self._canvas.create_text(
                centerx, centery, anchor='center',
                text="Game Over :(", font=('', 18, 'bold'),
                fill=utils.invert_color(self._canvas.cget('bg')))
        else:
            self._timeout_id = self._canvas.after(
                self._game.delay, self._on_timeout)

    def get_state(self) -> Game:
        return self._game       # it should be picklable

    @classmethod
    def from_state(cls, manager: tabs.TabManager, game: Game) -> 'TetrisTab':
        self = cls(manager)
        self._game = game
        self._refresh()
        self._timeout_id = self._canvas.after(game.delay, self._on_timeout)
        return self


def play_tetris() -> None:
    tab = TetrisTab(get_tab_manager())
    tab.new_game()
    get_tab_manager().add_tab(tab)


def setup() -> None:
    menubar.get_menu("Games").add_command(label="Tetris", command=play_tetris)
