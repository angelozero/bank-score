import os
import sys

from src.service.rag_service import execute

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

def main():
    print("Hello from bank-score!")
    execute()
    


if __name__ == "__main__":
    main()
