import subprocess as sp


def main():
    _ = sp.run(["ruff", "check"], check=True)
    _ = sp.run(["ruff", "format"], check=True)
    _ = sp.run(["basedpyright"], check=True)
    _ = sp.run(["pytest"], check=True)


if __name__ == "__main__":
    main()
