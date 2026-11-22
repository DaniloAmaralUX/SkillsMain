"""Only documented public fields may cross from authoring JSON into a delivery."""
from pathlib import PureWindowsPath


def fields(item, names):
    return {key: item[key] for key in names if key in item}


def public_project(project):
    """Project was already type-checked, including captions and local image paths."""
    public = fields(project, ("id", "name"))
    public["flows"] = [fields(flow, ("id", "title", "sum", "today")) for flow in project["flows"]]
    public["navigation"] = [fields(link, ("id", "label", "flow", "version")) for link in project["navigation"]]
    public["personas"] = {
        key: fields(value, ("name", "tag", "color", "ini", "line", "quote", "needs"))
        for key, value in project["personas"].items()
    }
    return public


def public_item(item, names):
    public = fields(item, names)
    public["evidence"] = []
    for ref in item["evidence"]:
        source = ref["source"]
        if PureWindowsPath(source).drive or "/" in source or "\\" in source or source.lower().startswith("file:"):
            raise ValueError("Use um nome público sem caminho em evidence.source. Mantenha o caminho em sources.json.")
        public["evidence"].append(fields(ref, ("source", "location", "excerpt")))
    return public


def public_delivery(data):
    public = fields(data, ("schema_version", "assumptions", "simulations", "limitations"))
    public["requirements"] = [
        public_item(row, ("id", "flow", "description", "acceptance")) for row in data["requirements"]
    ]
    public["open_questions"] = [public_item(row, ("kind", "question")) for row in data["open_questions"]]
    return public
