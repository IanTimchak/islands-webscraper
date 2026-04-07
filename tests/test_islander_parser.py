from scraper.parsers.islander import parse_islander_page


def test_parse_islander_page_basic() -> None:
    html = """
    <html>
      <head>
        <title>Kristjana Blomgren</title>
      </head>
      <body>
        <script>
          var id = 'j4vw2wjwr6';
          var chatid = '7nacdnqwjedqvgvnnw8m';
          var awake = 1;
        </script>

        <div id="t1">
          <table>
            <tr><th>Summary</th></tr>
            <tr><td>74 years old</td></tr>
            <tr><td>$262</td></tr>
            <tr><td>Lives in Vardo 6</td></tr>

            <tr><th>Age 0</th></tr>
            <tr><td>25/302</td><td>Born in Shinobi 351</td></tr>

            <tr><th>Age 3</th></tr>
            <tr><td>23/306</td><td>Friends with Akane Watanabe</td></tr>
          </table>
        </div>
      </body>
    </html>
    """

    result = parse_islander_page(html)

    assert result.name == "Kristjana Blomgren"
    assert result.islander_id == "j4vw2wjwr6"
    assert result.chatid == "7nacdnqwjedqvgvnnw8m"
    assert result.awake is True

    assert result.age == 74
    assert result.money_summary == "$262"
    assert result.current_residence == "Lives in Vardo 6"
    assert result.occupation_summary is None

    assert len(result.timeline_events) == 2
    assert result.timeline_events[0].age_stage == 0
    assert result.timeline_events[0].date_code == "25/302"
    assert result.timeline_events[0].text == "Born in Shinobi 351"