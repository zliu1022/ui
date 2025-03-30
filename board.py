#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#棋盘类（GoBoard） ：
#负责绘制棋盘，管理棋盘状态（例如，哪些位置有棋子，棋子的颜色等）。
#处理棋盘相关的操作，如落子、提子、检查棋组、判断气等。
#处理棋盘上的事件（如鼠标点击）。
#
#题目类（Problem） ：
#表示一个围棋题目，包含题目的所有信息，如初始位置、先手、难度、答案等。
#负责从数据库加载题目数据。

from pymongo import MongoClient
from pprint import pprint
from config import db_name

class GoBoard:
    def __init__(self, canvas, size=19, canvas_size=600, margin=50):
        self.canvas = canvas
        self.default_size = 19
        self.size = size
        self.canvas_size = canvas_size
        self.margin = margin
        self.default_cell_size = (canvas_size - 2 * margin) / (size - 1)
        self.cell_size = self.default_cell_size

        #存放棋子绘图元素
        self.stones = [[None for _ in range(size)] for _ in range(size)]

        #存放棋盘网格线绘图元素，坐标绘图，棋盘角落标识
        self.board = [[None for _ in range(2)] for _ in range(size)]
        self.coord = [[None for _ in range(4)] for _ in range(size)]
        self.corner = [None for _ in range(2)]

    # 清除棋盘网格线
    def clear_board(self):
        for i in range(self.size):
            self.canvas.delete(self.board[i][0])
            self.canvas.delete(self.board[i][1])
            self.board[i][0] = None
            self.board[i][1] = None
            
            self.canvas.delete(self.coord[i][0])
            self.canvas.delete(self.coord[i][1])
            self.canvas.delete(self.coord[i][2])
            self.canvas.delete(self.coord[i][3])
            self.coord[i][0] = None
            self.coord[i][1] = None
            self.coord[i][2] = None
            self.coord[i][3] = None
        self.canvas.delete(self.corner[0])
        self.canvas.delete(self.corner[1])

    # 绘制棋盘网格线
    def draw_board(self):
        max_x = self.margin + (self.size - 1) * self.cell_size
        max_y = self.margin + (self.size - 1) * self.cell_size
        for i in range(self.size):
            # Vertical lines
            x = self.margin + i * self.cell_size
            self.board[i][0] = self.canvas.create_line(x, self.margin, x, max_y)
            # Horizontal lines
            y = self.margin + i * self.cell_size
            self.board[i][1] = self.canvas.create_line(self.margin, y, max_x, y)

        self._draw_coordinates()

    # 绘制棋盘坐标
    def _draw_coordinates(self):
        max_x = self.margin + (self.size - 1) * self.cell_size
        max_y = self.margin + (self.size - 1) * self.cell_size
        
        columns = 'ABCDEFGHJKLMNOPQRST'
        for i in range(self.size):
            # 左侧坐标
            x_left = self.margin / 4
            y = self.margin + i * self.cell_size
            self.coord[i][0] = self.canvas.create_text(x_left, y, text=str(self.size - i))
            
            # 右侧坐标
            x_right = max_x + self.margin / 2
            self.coord[i][1] = self.canvas.create_text(x_right, y, text=str(self.size - i))
            
            # 顶部坐标
            x = self.margin + i * self.cell_size
            y_top = self.margin / 2
            self.coord[i][2] = self.canvas.create_text(x, y_top, text=columns[i])
            
            # 底部坐标
            y_bottom = max_y + 4*self.margin /5
            self.coord[i][3] = self.canvas.create_text(x, y_bottom, text=columns[i])

    # 从pa到15,0
    def coord_to_position(self, coord):
        columns = 'abcdefghijklmnopqrs'[:self.size]
        rows    = 'srqponmlkjihgfedcba'[:self.size]
        print(columns, rows, coord, '->', end=' ')
        col_letter, row_letter = coord[0], coord[1]
        col = columns.index(col_letter)
        row = rows.index(row_letter)
        row = self.size - row - 1  # Adjust row index to match the display
        print(col, row)
        return row, col

    def position_to_coord(self, row, col):
        columns = 'abcdefghijklmnopqrst'
        row_letter = columns[self.size - row - 1]
        col_letter = columns[col]
        return col_letter + row_letter

    def draw_stone(self, row, col, color):
        x = self.margin + col * self.cell_size
        y = self.margin + row * self.cell_size
        r = self.cell_size / 2 - 2
        stone = self.canvas.create_oval(x - r, y - r, x + r, y + r, fill=color)
        return stone

    def draw_hint(self, coord):
        row, col = self.coord_to_position(coord)
        x = self.margin + col * self.cell_size
        y = self.margin + row * self.cell_size
        r = self.cell_size / 2 - 2
        hint = self.canvas.create_oval(x - r, y - r, x + r, y + r, outline='red', width=2)
        return hint

    def clear_stones(self):
        for row in range(self.size):
            for col in range(self.size):
                if self.stones[row][col] is not None:
                    self.canvas.delete(self.stones[row][col]['stone'])
                    if self.stones[row][col]['label'] is not None:
                        self.canvas.delete(self.stones[row][col]['label'])
                    self.stones[row][col] = None

    def place_preset_stones(self, prepos):
        for color, positions in prepos.items():
            for coord in positions:
                row, col = self.coord_to_position(coord)
                x = self.margin + col * self.cell_size
                y = self.margin + row * self.cell_size
                r = self.cell_size / 2 - 2
                stone_color = 'black' if color == 'b' else 'white'
                stone = self.canvas.create_oval(x - r, y - r, x + r, y + r, fill=stone_color, tags='preset_stone')
                self.stones[row][col] = {'color': stone_color, 'stone': stone, 'label': None}

class GoProblem:
    def __init__(self, problem_data=None):
        self.problem_data = problem_data or {}
        self.prepos = self.problem_data.get('prepos', {})
        self.blackfirst = self.problem_data.get('blackfirst', True)
        self.level = self.problem_data.get('level', 'N/A')
        self.answers = self.problem_data.get('answers', [])
        self.publicid = self.problem_data.get('publicid', 'N/A')
        self.ty = self.problem_data.get('qtype', 'N/A')

        self.size = self.problem_data.get('size', 19)

    @staticmethod
    def load_problems_from_db(criteria):
        client = MongoClient('mongodb://localhost:27017/')
        db = client[db_name]
        collection = db['q']
        problems_cursor = collection.find(criteria)
        problems_data = list(problems_cursor)
        problems = [GoProblem(problem_data) for problem_data in problems_data]
        return problems
