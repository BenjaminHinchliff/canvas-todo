import os
import dateutil.parser

from canvasapi import Canvas
from canvasapi.canvas import PaginatedList
from canvasapi.todo import Todo

from textual.app import App, ComposeResult
from textual.reactive import reactive
from textual.widgets import Button, Footer, Header, Static, Label
from textual.css.query import NoMatches

from bs4 import BeautifulSoup
from bs4.element import Tag

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

API_URL = os.getenv("CANVAS_API_URL")
API_TOKEN = os.getenv("CANVAS_API_TOKEN")
AM_PM = os.getenv("DUE_DATE_AM_PM")
AM_PM = False if AM_PM is None else AM_PM

if API_URL is None or API_TOKEN is None:
    raise SystemExit("CANVAS_API_URL and CANVAS_API_TOKEN"
                     "must be defined in the environment")


class TodoNode(Button):

    def __init__(self, todo: Todo) -> None:
        super().__init__(todo.assignment["name"], classes="todo-node")
        self.todo = todo


class TodosList(Static):
    todos: reactive[PaginatedList | None] = reactive(None)

    async def watch_todos(self, old_todos: PaginatedList | None,
                          new_todos: PaginatedList | None) -> None:
        if new_todos != old_todos:
            # am lazy use brute force
            for node in self.query(".todo-node"):
                node.remove()
            if new_todos is not None:
                for todo in new_todos:
                    self.mount(TodoNode(todo))


class Details(Static):
    todo: reactive[Todo | None] = reactive(None)

    def tag_to_rich(tag: Tag) -> str:
        if tag.name is None:
            return tag.string

        children = "".join(
            Details.tag_to_rich(child) for child in tag.children)

        if tag.name == "strong":
            return f"[bold]{children}[not bold]"
        elif tag.name == "em":
            return f"[italic]{children}[not italic]"
        elif tag.name == "span" and tag.has_attr("style"):
            if tag["style"] == "text-decoration: underline;":
                return f"[underline]{children}[not underline]"
            elif tag["style"] == "text-decoration: line-through;":
                return f"[strike]{children}[not strike]"
            else:
                return children
        else:
            return children

    def watch_todo(self, todo: Todo | None) -> None:
        if todo is not None:
            self.query_one("#course").update(todo.context_name)
            self.query_one("#title").update(todo.assignment["name"])

            due_date = self.query_one("#due-date")
            if todo.assignment["due_at"] is not None:
                due_at = (dateutil.parser.isoparse(
                    todo.assignment["due_at"]).astimezone().strftime(
                        f"%a %b %d %Y {'%I' if AM_PM else '%H'}:%M"
                        f"{'%p' if AM_PM else ''}"))

                due_date.update(f"Due: {due_at}")
            else:
                due_date.update("")

            description = self.query_one("#description")
            if todo.assignment["description"] is not None:
                soup = BeautifulSoup(todo.assignment["description"],
                                     features="html.parser")
                rich_text = "".join(
                    Details.tag_to_rich(tag) for tag in soup.children)

                description.update(rich_text)
            else:
                description.update("")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close":
            self.remove()

    def compose(self) -> ComposeResult:
        yield Button("close", id="close")
        yield Label("", id="course")
        yield Label("", id="title")
        yield Label("", id="due-date")
        yield Label("", id="description")


class CanvasTodoApp(App):
    CSS_PATH = "todo.css"
    BINDINGS = [("d", "toggle_dark", "Toggle dark mode")]

    canvas: Canvas | None = None

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if "todo-node" in event.button.classes:
            try:
                details = self.query_one("#details")
            except NoMatches:
                details = Details(id="details")
                await self.mount(details)
            details.todo = event.button.todo

    def update_todos(self) -> None:
        if self.canvas is None:
            self.canvas = Canvas(API_URL, API_TOKEN)
        self.query_one("#todos").todos = self.canvas.get_todo_items()

    def on_mount(self) -> None:
        self.update_todos()
        self.set_interval(60.0, self.update_todos)

    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()
        yield TodosList(id="todos")


if __name__ == "__main__":
    app = CanvasTodoApp()
    app.run()
