#!/usr/bin/env python3
"""
四則演算CLIツール
使用方法: python calculator.py <数値1> <演算子> <数値2>
演算子: +, -, *, /
"""

import sys
import argparse


def add(a, b):
    """加算"""
    return a + b


def subtract(a, b):
    """減算"""
    return a - b


def multiply(a, b):
    """乗算"""
    return a * b


def divide(a, b):
    """除算"""
    if b == 0:
        raise ValueError("ゼロで除算することはできません")
    return a / b


def calculate(num1, operator, num2):
    """計算を実行する"""
    operations = {
        '+': add,
        '-': subtract,
        '*': multiply,
        '/': divide
    }
    
    if operator not in operations:
        raise ValueError(f"サポートされていない演算子: {operator}")
    
    return operations[operator](num1, num2)


def main():
    parser = argparse.ArgumentParser(
        description='四則演算CLIツール',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python calculator.py 10 + 5
  python calculator.py 20 - 8
  python calculator.py 6 \\* 7  # シェルでは*をエスケープ
  python calculator.py 15 / 3
        """
    )
    
    parser.add_argument('num1', type=float, help='第1数値')
    parser.add_argument('operator', choices=['+', '-', '*', '/'], help='演算子 (+, -, *, /)')
    parser.add_argument('num2', type=float, help='第2数値')
    parser.add_argument('-v', '--verbose', action='store_true', help='詳細出力')
    
    try:
        args = parser.parse_args()
        
        result = calculate(args.num1, args.operator, args.num2)
        
        if args.verbose:
            print(f"{args.num1} {args.operator} {args.num2} = {result}")
        else:
            print(result)
            
    except ValueError as e:
        print(f"エラー: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"予期しないエラー: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()