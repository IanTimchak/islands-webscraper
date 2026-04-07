import typer

app = typer.Typer(help="Islands webscraper CLI")


@app.callback()
def main() -> None:
    """Root CLI app."""
    pass


@app.command()
def hello() -> None:
    """Test command."""
    print("islands-webscraper is set up")


if __name__ == "__main__":
    app()