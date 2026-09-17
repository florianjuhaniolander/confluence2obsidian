from confluence2obsidian.converter import storage_to_markdown


def test_basic_html_to_markdown():
    result = storage_to_markdown("<h2>Hello</h2><p>World <strong>bold</strong></p>")
    assert "## Hello" in result
    assert "**bold**" in result


def test_info_macro_to_callout():
    storage = """
    <ac:structured-macro ac:name="info">
      <ac:parameter ac:name="title">Heads up</ac:parameter>
      <ac:rich-text-body><p>Important text</p></ac:rich-text-body>
    </ac:structured-macro>
    """
    result = storage_to_markdown(storage)
    assert "> [!info] Heads up" in result
    assert "> Important text" in result


def test_code_macro():
    storage = """
    <ac:structured-macro ac:name="code">
      <ac:parameter ac:name="language">python</ac:parameter>
      <ac:plain-text-body>print(&quot;hi&quot;)</ac:plain-text-body>
    </ac:structured-macro>
    """
    result = storage_to_markdown(storage)
    assert "```python" in result
    assert 'print("hi")' in result


def test_page_link_to_wikilink():
    storage = """
    <p>See <ac:link><ri:page ri:content-title="Background" /></ac:link>.</p>
    """
    result = storage_to_markdown(storage, {"Background": "Lab/GPCR Design/Background"})
    assert "[[Lab/GPCR Design/Background|Background]]" in result


def test_image_attachment_to_embed():
    storage = '<ac:image><ri:attachment ri:filename="figure.png" /></ac:image>'
    result = storage_to_markdown(storage)
    assert "![[figure.png]]" in result


def test_unknown_macro_is_not_silently_dropped():
    storage = """
    <ac:structured-macro ac:name="mystery-widget">
      <ac:rich-text-body><p>Keep me</p></ac:rich-text-body>
    </ac:structured-macro>
    """
    result = storage_to_markdown(storage)
    assert "Unsupported Confluence macro" in result
    assert "Keep me" in result
