from scraper.parsers.village import parse_village_page


def test_parse_village_page_basic() -> None:
    html = """
    <html>
      <script>
        var island = 0;
        var village = 'Vardo';
        var v = 0;
        var map = [['house', 0, 2, 0, 0],['house', 5, 2, 0, 0],['school', 'school', 0, 0, 0],['house', 12, 2, 0, 0]];
      </script>
    </html>
    """

    result = parse_village_page(html)

    assert result.village_name == "Vardo"
    assert result.village_id == 0
    assert result.island_id == 0
    assert result.house_ids == [0, 5, 12]