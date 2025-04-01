#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pymongo import MongoClient
from pprint import pprint
from config import db_name, letter_to_num, full_board_size

#棋盘类（GoBoard） ：
#负责绘制棋盘，管理棋盘状态（例如，哪些位置有棋子，棋子的颜色等）。
#处理棋盘相关的操作，如落子、提子、检查棋组、判断气等。
#处理棋盘上的事件（如鼠标点击）。
class GoBoard:
    def __init__(self, canvas, size=full_board_size, canvas_size=600, margin=50):
        self.canvas = canvas
        self.size = size
        self.canvas_size = canvas_size
        self.margin = margin
        self.cell_size = (canvas_size - 2 * margin) / (size - 1)

        # 棋盘view范围
        self.min_row = 0
        self.min_col = 0
        self.max_row = self.size - 1
        self.max_col = self.size - 1

        #存放棋子绘图元素
        self.stones = [[None for _ in range(full_board_size)] for _ in range(full_board_size)]

        #存放棋盘网格线绘图元素，坐标绘图
        self.board = [[None for _ in range(2)] for _ in range(full_board_size)]
        self.board_border = [None for _ in range(4)]
        self.coord = [[None for _ in range(4)] for _ in range(full_board_size)]

    # 根据题目中的size改变棋盘大小，边缘、格子大小也按比例变化
    def change_size(self, new_size):
        self.size = new_size
        if new_size == full_board_size or new_size >= 7:
            self.margin = 50
        else:
            self.margin = 1.5 * 50
        self.cell_size = (self.canvas_size - 2 * self.margin) / (new_size - 1)

        # 重置棋盘view范围
        self.min_row = 0
        self.min_col = 0
        self.max_row = self.size - 1
        self.max_col = self.size - 1

    # 清除棋盘网格线，坐标
    def clear_board(self):
        # 清除棋盘网格线
        for i in range(full_board_size):
            for j in range(2):
                if self.board[i][j] is not None:
                    self.canvas.delete(self.board[i][j])
                    self.board[i][j] = None
        for i in range(4):
            if self.board_border[i] is not None:
                self.canvas.delete(self.board_border[i])
                self.board_border[i] = None
        # 清除棋盘坐标
        for i in range(full_board_size):
            for j in range(4):
                if self.coord[i][j] is not None:
                    self.canvas.delete(self.coord[i][j])
                    self.coord[i][j] = None

    # 绘制棋盘网格线
    def draw_board(self, min_row=None, max_row=None, min_col=None, max_col=None):
        # Update board extents if provided
        if min_row is not None:
            self.min_row = min_row
        if min_col is not None:
            self.min_col = min_col
        if max_row is not None:
            self.max_row = max_row
        if max_col is not None:
            self.max_col = max_col

        num_rows = self.max_row - self.min_row + 1
        num_cols = self.max_col - self.min_col + 1

        # Recalculate cell_size to fit the canvas
        self.cell_size = (self.canvas_size - 2 * self.margin) / (max(num_rows - 1, num_cols - 1))

        max_x = self.margin + (num_cols - 1) * self.cell_size
        max_y = self.margin + (num_rows - 1) * self.cell_size

        # Draw vertical lines
        for idx_col in range(num_cols):
            x = self.margin + idx_col * self.cell_size
            self.board[idx_col][0] = self.canvas.create_line(x, self.margin, x, max_y)
        # Draw horizontal lines
        for idx_row in range(num_rows):
            y = self.margin + idx_row * self.cell_size
            self.board[idx_row][1] = self.canvas.create_line(self.margin, y, max_x, y)

        # Draw border lines if the view includes board edges
        border_width = 1
        border_gap = 2
        # Top border
        if self.min_row == 0:
            self.board_border[0] = self.canvas.create_line(self.margin-2*border_gap, self.margin-2*border_gap, max_x+2*border_gap, self.margin-2*border_gap, width=border_width)
        # Bottom border
        if self.max_row == self.size - 1:
            self.board_border[1] = self.canvas.create_line(self.margin-2*border_gap, max_y+2*border_gap, max_x+2*border_gap, max_y+2*border_gap, width=border_width)
        # Left border
        if self.min_col == 0:
            self.board_border[2] = self.canvas.create_line(self.margin-2*border_gap, self.margin-2*border_gap, self.margin-2*border_gap, max_y+2*border_gap, width=border_width)
        # Right border
        if self.max_col == self.size - 1:
            self.board_border[3] = self.canvas.create_line(max_x+2*border_gap, self.margin-2*border_gap, max_x+2*border_gap, max_y+2*border_gap, width=border_width)

        self._draw_coordinates(max_x, max_y)

    # 绘制棋盘坐标
    def _draw_coordinates(self, max_x, max_y):
        columns = 'ABCDEFGHJKLMNOPQRST'  # Go columns (I is skipped)
        # Draw column labels (top and bottom)
        for idx_col, col in enumerate(range(self.min_col, self.max_col + 1)):
            x = self.margin + idx_col * self.cell_size
            column_label = columns[col]
            y_top = self.margin / 3
            self.coord[col][2] = self.canvas.create_text(x, y_top, text=column_label)
            y_bottom = max_y + 2 * self.margin / 3
            self.coord[col][3] = self.canvas.create_text(x, y_bottom, text=column_label)
        # Draw row labels (left and right)
        for idx_row, row in enumerate(range(self.min_row, self.max_row + 1)):
            y = self.margin + idx_row * self.cell_size
            row_label = str(self.size - row)
            x_left = self.margin / 3
            self.coord[row][0] = self.canvas.create_text(x_left, y, text=row_label)
            x_right = max_x + 2 * self.margin / 3
            self.coord[row][1] = self.canvas.create_text(x_right, y, text=row_label)

    # 从aa转换到0,0，不跳过i
    def coord_to_position(self, coord):
        col_letter, row_letter = coord[0], coord[1]
        col = letter_to_num[col_letter]
        row = letter_to_num[row_letter]
        return row, col

    # 从0,0到画布像素坐标
    def position_to_canvas(self, row, col):
        x = self.margin + (col - self.min_col) * self.cell_size
        y = self.margin + (row - self.min_row) * self.cell_size
        return x, y

    # 绘制棋子
    def draw_stone(self, row, col, color):
        x, y = self.position_to_canvas(row, col)
        r = self.cell_size / 2
        stone = self.canvas.create_oval(x - r, y - r, x + r, y + r, fill=color)
        return stone

    def draw_stone_number(self, row, col, color, number):
        x, y = self.position_to_canvas(row, col)
        label_color = 'white' if color == 'black' else 'black'
        label = self.canvas.create_text(x, y, text=str(number), fill=label_color)
        return label

    # 绘制答案位置的提示标志
    def draw_hint(self, coord):
        row, col = self.coord_to_position(coord)
        x, y = self.position_to_canvas(row, col)
        r = self.cell_size / 2 - 2
        hint = self.canvas.create_oval(x - r, y - r, x + r, y + r, outline='red', width=2)
        return hint

    # 清除棋子
    def clear_stones(self):
        for row in range(self.size):
            for col in range(self.size):
                if self.stones[row][col] is not None:
                    self.canvas.delete(self.stones[row][col]['stone'])
                    if self.stones[row][col]['label'] is not None:
                        self.canvas.delete(self.stones[row][col]['label'])
                    self.stones[row][col] = None

    # 摆放死活题中的黑白棋子
    def place_preset_stones(self, prepos):
        for color, positions in prepos.items():
            for coord in positions:
                row, col = self.coord_to_position(coord)
                x, y = self.position_to_canvas(row, col)
                r = self.cell_size / 2 - 2
                stone_color = 'black' if color == 'b' else 'white'
                stone = self.canvas.create_oval(x - r, y - r, x + r, y + r, fill=stone_color)
                self.stones[row][col] = {'color': stone_color, 'stone': stone, 'label': None}

#题目类（Problem） ：
#表示一个围棋题目，包含题目的所有信息，如初始位置、先手、难度、答案等。
#负责从数据库加载题目数据。
class GoProblem:
    def __init__(self, problem_data=None):
        self.problem_data = problem_data or {}
        self.prepos = self.problem_data.get('prepos', {})
        self.blackfirst = self.problem_data.get('blackfirst', True)
        self.level = self.problem_data.get('level', 'N/A')
        self.answers = self.problem_data.get('answers', [])
        self.publicid = self.problem_data.get('publicid', 'N/A')
        self.qtype = self.problem_data.get('qtype', 'N/A')
        self.size = self.problem_data.get('size', full_board_size)

    @staticmethod
    def load_problems_from_db(criteria):
        client = MongoClient('mongodb://localhost:27017/')
        db = client[db_name]
        collection = db['q']
        problems_cursor = collection.find(criteria)
        problems_data = list(problems_cursor)
        problems = [GoProblem(problem_data) for problem_data in problems_data]
        return problems

    #  calculate the board extent needed by the problem
    def get_board_extent(self):
        positions = set()

        # Positions from prepos
        for color, coords in self.prepos.items():
            for coord in coords:
                col_char, row_char = coord[0], coord[1]
                col_index = letter_to_num[col_char]
                row_index = letter_to_num[row_char]
                positions.add((row_index, col_index))

        # Positions from answers
        for answer in self.answers:
            for coord in answer['p']:
                col_char, row_char = coord[0], coord[1]
                col_index = letter_to_num[col_char]
                row_index = letter_to_num[row_char]
                positions.add((row_index, col_index))

        if positions:
            rows, cols = zip(*positions)
            min_row, max_row = min(rows), max(rows)
            min_col, max_col = min(cols), max(cols)
            return min_row, max_row, min_col, max_col
        else:
            # Default to full board if positions are not found
            return 0, 18, 0, 18
