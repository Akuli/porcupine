# TODO: add a pause feature (maybe pressing p or something?)
import functools
import itertools
import random
import tkinter as tk

import porcupine
from porcupine import tabs, utils

WIDTH = 10
HEIGHT = 20
SCALE = 20     # each square is 20x20 pixels


# the shapes are lists of (x, y) coordinates where (0, 0) is the point
# that the shape rotates around and top center of the game when the
# shape is added to it
# y is like in math, so more y means higher
SHAPES = {          # noqa
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
            (0, 1),
            (0, 0),
  (-1, -1), (0, -1)],
    'S': [
            (0, 1), (1, 1),
   (-1, 0), (0, 0)],
    'Z': [(-1, 1), (0, 1),
                   (0, 0), (1, 0)],
}


class Block:
    """The block that is currently moving down the game.

    Other blocks end up in Game.frozen_squares.
    """

    def __init__(self, game, shape_letter):
        self._game = game
        self.shape_letter = shape_letter
        self.shape = SHAPES[shape_letter].copy()
        self.x = WIDTH // 2
        self.y = HEIGHT

    # for debugging
    def __repr__(self):
        coords = (self.x, self.y)
        return '<%s-shaped %s at %r>' % (
            self.shape_letter, type(self).__name__, coords)

    def get_coords(self):
        for shapex, shapey in self.shape:
            yield (self.x + shapex, self.y + shapey)

    def bumps(self, x, y):
        return (x not in range(WIDTH)
                or y < 0
                or (x, y) in self._game.frozen_squares)

    def _move(self, deltax, deltay):
        for x, y in self.get_coords():
            if self.bumps(x + deltax, y + deltay):
                return False

        self.x += deltax
        self.y += deltay
        return True

    move_left = functools.partialmethod(_move, -1, 0)
    move_right = functools.partialmethod(_move, +1, 0)
    move_down = functools.partialmethod(_move, 0, -1)

    def move_down_all_the_way(self):
        while self.move_down():
            pass

    def rotate(self):
        new_shape = []
        for old_x, old_y in self.shape:
            x, y = -old_y, old_x
            if self.bumps(self.x + x, self.y + y):
                return False
            new_shape.append((x, y))

        self.shape[:] = new_shape
        return True


class NonRotatingBlock(Block):

    def rotate(self):
        return False


class TwoRotationsBlock(Block):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rotations = None

    def rotate(self):
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
                    return False
            self.shape = new_shape
            return True


class Game:

    def __init__(self):
        self.moving_block = None
        self.frozen_squares = {}   # {(x, y): shape_letter}
        self.score = 0      # each new block increments score
        self.add_block()

    @property
    def level(self):
        # levels start at 1
        return self.score//30 + 1    # noqa

    @property
    def delay(self):
        """The waiting time between do_something() calls as milliseconds."""
        return 300 - (30 * self.level)

    def add_block(self):
        letter = random.choice(list(SHAPES))
        if letter == 'O':
            self.moving_block = NonRotatingBlock(self, letter)
        elif letter in {'I', 'S', 'Z'}:
            self.moving_block = TwoRotationsBlock(self, letter)
        else:
            self.moving_block = Block(self, letter)

    def shape_at(self, x, y):
        try:
            return self.frozen_squares[(x, y)]
        except KeyError:
            if (x, y) in self.moving_block.get_coords():
                return self.moving_block.shape_letter
            return None

    def freeze_moving_block(self):
        for x, y in self.moving_block.get_coords():
            self.frozen_squares[(x, y)] = self.moving_block.shape_letter

    def delete_full_lines(self):
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

    def do_something(self):
        if self.moving_block.move_down():
            return

        self.freeze_moving_block()
        self.add_block()
        self.delete_full_lines()
        self.score += 1

    def game_over(self):
        """Return True if the game is over."""
        for x in range(WIDTH):
            if (x, HEIGHT) in self.frozen_squares:
                return True
        return False


COLORS = {
    'I': 'red',
    'O': 'blue',
    'T': 'yellow',
    'L': 'magenta',
    'J': 'white',
    'S': 'green',
    'Z': 'cyan',
}


class TetrisTab(tabs.Tab):

    def __init__(self, manager):
        super().__init__(manager)
        self.top_label['text'] = "Tetris"

        # the takefocus thing is important, it's hard to bind the keys
        # correctly without it
        self._canvas = tk.Canvas(
            self, width=WIDTH*SCALE, height=HEIGHT*SCALE,
            relief='ridge', bg='black', takefocus=True)
        self._canvas.pack()

        # this also requires binding on the tab when the tab is detached
        for key in ['<A>', '<a>', '<S>', '<s>', '<D>', '<d>', '<F>', '<f>',
                    '<Left>', '<Right>', '<Up>', '<Down>', '<Return>',
                    '<space>', '<F2>']:
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

        self._timeout_id = None
        self._game_over_id = None
        self.new_game()

    def _on_key(self, event):
        if event.keysym in {'A', 'a', 'Left'}:
            self._game.moving_block.move_left()
        elif event.keysym in {'D', 'd', 'Right'}:
            self._game.moving_block.move_right()
        elif event.keysym in {'Return', 'Up'}:
            self._game.moving_block.rotate()
        elif event.keysym in {'space', 'Down'}:
            self._game.moving_block.move_down_all_the_way()
        elif event.keysym == 'F2':
            self.new_game()
        else:
            raise ValueError("unknown keysym %r" % event.keysym)

        self._refresh()
        return 'break'

    def _refresh(self):
        for (x, y), item_id in self._canvas_content.items():
            shape = self._game.shape_at(x, y)
            if shape is None:
                color = self._canvas['bg']
            else:
                color = COLORS[shape]
            self._canvas.itemconfig(item_id, fill=color)

        self.status = "Score %d, level %d" % (
            self._game.score, self._game.level)

    def new_game(self, junk_event=None):
        if self._timeout_id is not None:
            self.after_cancel(self._timeout_id)
        if self._game_over_id is not None:
            self._canvas.delete(self._game_over_id)
            self._game_over_id = None

        self._game = Game()
        self._refresh()
        self._on_timeout()

    def _on_timeout(self):
        self._game.do_something()
        self._refresh()

        if self._game.game_over():
            centerx = int(self._canvas['width']) // 2
            centery = int(self._canvas['height']) // 3
            self._game_over_id = self._canvas.create_text(
                centerx, centery, anchor='center',
                text="Game Over :(", font=('', 18, 'bold'),
                fill=utils.invert_color(self._canvas['bg']))
        else:
            self._timeout_id = self._canvas.after(
                self._game.delay, self._on_timeout)

    def on_focus(self):
        # yes, this needs force for some reason
        self._canvas.focus_force()


def play_tetris():
    manager = porcupine.get_tab_manager()
    manager.add_tab(TetrisTab(manager))


def setup():
    porcupine.add_action(play_tetris, 'Games/Tetris')
