from dotenv import load_dotenv

from src.cl4.server import cl

if __name__ == "__main__":
    load_dotenv()

    cl.run(ip="0.0.0.0", port=3001)
