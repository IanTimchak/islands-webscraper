from scraper.parsers.house import parse_household_page


def test_parse_household_page_basic() -> None:
    html = """
    <h4 class="house">House 6</h4>
    <table class="residents">
      <tr>
        <td class="resident"><a href="islander.php?id=j4vw2wjwr6">Kristjana Blomgren</a></td>
        <td class="age">74</td>
      </tr>
      <tr>
        <td class="resident"><a href="islander.php?id=8kk94lu5yy">Akane Watanabe</a></td>
        <td class="age">74</td>
      </tr>
    </table>
    """

    result = parse_household_page(
        html,
        village_id=0,
        requested_house_id=5,
    )

    assert result.village_id == 0
    assert result.house_id == 5
    assert result.display_house_number == 6
    assert len(result.residents) == 2

    assert result.residents[0].name == "Kristjana Blomgren"
    assert result.residents[0].age == 74
    assert result.residents[0].islander_id == "j4vw2wjwr6"