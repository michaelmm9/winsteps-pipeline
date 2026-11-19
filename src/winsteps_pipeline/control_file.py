"""Generate a WINSTEPS control file from a project configuration and a template."""
from pathlib import Path
from string import Template

from .config import validate_data_file


def render_control_file(cfg, template_path, embed_data=True, request_output_files=False):
    """Return the text of a control file.

    cfg                  a validated ProjectConfig
    template_path        path to the template (.tpl) with $placeholders
    embed_data           True: data lines go after END NAMES (the layout of our practice file)
                         False: a DATA= line points to the data file instead
    request_output_files True: add IFILE= and PFILE= lines so the item and person
                         tables are written to predictable file names
    """
    # rstrip("\n"): editors often add a trailing newline, which would add a blank last line
    template = Template(Path(template_path).read_text(encoding="utf-8").rstrip("\n"))

    # Optional settings are built in Python, one line each, each ending in a newline.
    # If there are none, this is an empty string and leaves no blank line behind.
    extra = []
    if request_output_files:
        extra.append(f"IFILE = {cfg.output_dir / cfg.item_file}")
        extra.append(f"PFILE = {cfg.output_dir / cfg.person_file}")
    if not embed_data:
        extra.append(f"DATA = {cfg.data_file}")
    extra_settings = "".join(line + "\n" for line in extra)

    data_block = ""
    if embed_data:
        with cfg.data_file.open(encoding="utf-8") as f:
            lines = [line.rstrip("\r\n") for line in f if line.strip()]
        data_block = "\n".join(lines) + "\n"

    # substitute() raises an error if the template uses a placeholder we did not supply,
    # which is what we want: a typo in a template should fail loudly.
    return template.substitute(
        title=cfg.title,
        n_items=cfg.n_items,
        item_first_column=cfg.item_first_column,
        person_label_start=cfg.person_label_start,
        person_label_length=cfg.person_label_length,
        codes=cfg.codes,
        extra_settings=extra_settings,
        item_labels="\n".join(cfg.item_labels),
        data_block=data_block,
    )


def write_control_file(cfg, template_path, destination, **options):
    """Validate the data against the config, then write the control file."""
    n_records = validate_data_file(cfg)          # refuse to generate from bad inputs
    text = render_control_file(cfg, template_path, **options)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="\r\n") as f:   # Windows line endings
        f.write(text)
    return n_records