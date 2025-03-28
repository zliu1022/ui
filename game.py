#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#游戏逻辑类（Game） ：
#处理游戏的规则和逻辑，如判断合法性、轮到谁下棋、胜负判定等。
#管理题目加载、答案验证等功能。

import random
from board import GoProblem

class GoGame:
    def __init__(self, board):
        self.board = board
        self.user_moves = []
        self.current_color = None
        self.move_number = 1
        self.hint_items = []
        self.black_captures = 0
        self.white_captures = 0
        self.problems = []
        self.current_problem = None
        self.current_problem_index = -1

    def load_problems(self):
        self.problems = GoProblem.load_problems_from_db({"status": 2, "qtype": "死活题", "level": "9K"})
        if not self.problems:
            raise Exception("No problems found")

    def load_problem(self, index=None):
        if index is None:
            self.current_problem_index = random.randint(0, len(self.problems) - 1)
            self.current_problem = self.problems[self.current_problem_index]
        else:
            self.current_problem_index = index
            self.current_problem = self.problems[index]

        self.reset_game()
        self.current_color = 'black' if self.current_problem.blackfirst else 'white'

        # Place preset stones
        self.board.place_preset_stones(self.current_problem.prepos)

        # Display hint for the first move
        first_move = None
        if self.current_problem.answers:
            for ans in self.current_problem.answers:
                if ans['ty'] == 1 and ans['st'] == 2:
                    first_move = ans['p'][0]
                    break
            if first_move is None:
                print('Warning no answers ty==1 st==2')
                first_move = 'jj'
            self.hint_items.append(self.board.draw_hint(first_move))

        return {
            'level': self.current_problem.level,
            'color': 'Black' if self.current_problem.blackfirst else 'White',
            'problem_no': self.current_problem.publicid,
            'type': self.current_problem.ty
        }

    def reset_game(self):
        self.board.clear_board()
        self.user_moves = []
        self.move_number = 1

        # Clear previous hints
        for item in self.hint_items:
            self.board.canvas.delete(item)
        self.hint_items.clear()

        self.black_captures = 0
        self.white_captures = 0

    def get_group(self, row, col):
        color = self.board.board[row][col]['color']
        group = set()
        stack = [(row, col)]
        while stack:
            r, c = stack.pop()
            if (r, c) not in group:
                group.add((r, c))
                # Check the four neighbors
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < self.board.size and 0 <= nc < self.board.size:
                        if self.board.board[nr][nc] is not None and self.board.board[nr][nc]['color'] == color:
                            stack.append((nr, nc))
        return group

    def has_liberties(self, group):
        for r, c in group:
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < self.board.size and 0 <= nc < self.board.size:
                    if self.board.board[nr][nc] is None:
                        return True
        return False

    def remove_group(self, group):
        for r, c in group:
            self.board.canvas.delete(self.board.board[r][c]['stone'])
            if self.board.board[r][c]['label'] is not None:
                self.board.canvas.delete(self.board.board[r][c]['label'])
            self.board.board[r][c] = None

    def get_expected_coords(self, move_number):
        expected_coords = set()
        for answer in self.current_problem.answers:
            if len(answer['p']) >= move_number:
                expected_coords.add(answer['p'][move_number - 1])
        return expected_coords

    def get_expected_next_coords(self, user_moves):
        expected_coords = set()
        for answer in self.current_problem.answers:
            if answer['p'][:len(user_moves)] == user_moves:
                if len(answer['p']) > len(user_moves):
                    expected_coords.add(answer['p'][len(user_moves)])
        return expected_coords

    def make_move(self, row, col):
        # Check if the position is unoccupied
        if self.board.board[row][col] is not None:
            messagebox.showwarning("Invalid move", "That position is occupied.")
            return 'invalid_move'

        # Get expected coordinates for the current move number
        expected_coords = self.get_expected_coords(self.move_number)
        tolerance = self.board.cell_size / 2  # Allowable distance from the correct point
        match_found = False
        coord = None

        for exp_coord in expected_coords:
            exp_row, exp_col = self.board.coord_to_position(exp_coord)
            if (exp_row, exp_col) == (row, col):
                coord = exp_coord
                match_found = True
                break

        if not match_found:
            return 'incorrect'  # 返回'错误'状态

        # Place the stone tentatively
        stone = self.board.draw_stone(row, col, self.current_color)
        label_color = 'white' if self.current_color == 'black' else 'black'
        label = self.board.canvas.create_text(
            self.board.margin + col * self.board.cell_size,
            self.board.margin + row * self.board.cell_size,
            text=str(self.move_number), fill=label_color)
        self.board.board[row][col] = {'color': self.current_color, 'stone': stone, 'label': label}

        # Perform captures
        opponent_color = 'white' if self.current_color == 'black' else 'black'
        captured_stones = 0

        # Check adjacent positions for opponent stones
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = row + dr, col + dc
            if 0 <= nr < self.board.size and 0 <= nc < self.board.size:
                if self.board.board[nr][nc] is not None and self.board.board[nr][nc]['color'] == opponent_color:
                    opponent_group = self.get_group(nr, nc)
                    if not self.has_liberties(opponent_group):
                        self.remove_group(opponent_group)
                        captured_stones += len(opponent_group)
                        # Record captures
                        if self.current_color == 'black':
                            self.black_captures += len(opponent_group)
                        else:
                            self.white_captures += len(opponent_group)

        # Now check if own group has liberties
        own_group = self.get_group(row, col)
        if not self.has_liberties(own_group):
            # Invalid move: self-capture not allowed
            # Remove the placed stone
            self.board.canvas.delete(self.board.board[row][col]['stone'])
            self.board.canvas.delete(self.board.board[row][col]['label'])
            self.board.board[row][col] = None
            return 'invalid_move'

        # The move is valid, proceed
        self.user_moves.append(coord)
        self.move_number += 1

        # Switch color
        self.current_color = 'white' if self.current_color == 'black' else 'black'

        # Clear previous hints
        for item in self.hint_items:
            self.board.canvas.delete(item)
        self.hint_items.clear()

        # Check if the user's sequence matches any of the answers
        matched_answers = []
        for answer in self.current_problem.answers:
            answer_moves = answer['p']
            if self.user_moves == answer_moves[:len(self.user_moves)]:
                matched_answers.append(answer)
                if len(self.user_moves) == len(answer_moves):
                    return 'correct'  # 返回'正确'状态
                break  # Found a matching answer

        # Display hints for the next expected moves
        next_expected_coords = self.get_expected_next_coords(self.user_moves)
        for coord in next_expected_coords:
            self.hint_items.append(self.board.draw_hint(coord))

        return 'continue'  # 返回'继续'状态
