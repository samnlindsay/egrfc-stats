import altair as alt
from bs4 import BeautifulSoup

VEGA_ACTIONS = {
    "export": True,
    "source": False,
    "compiled": False,
    "editor": False,
}

VEGA_ACTIONS_MENU_CSS = '''

      .vega-embed {
          display: block !important;
          position: relative;
      }

      .vega-embed.has-actions {
          padding: 0 !important;
      }

      #vis.vega-embed {
          display: block !important;
      }

      .vega-embed > details,
      .vega-embed details[title="Click to view actions"] {
          position: absolute !important;
          top: 8px;
          right: 8px;
          left: auto !important;
          margin: 0;
          float: none !important;
          z-index: 10;
      }

      .vega-embed > details > summary,
      .vega-embed details[title="Click to view actions"] > summary {
          position: absolute !important;
          top: 0;
          right: 50px !important;
          left: auto !important;
      }

      .vega-embed > details > .vega-actions,
      .vega-embed details[title="Click to view actions"] > .vega-actions {
          position: absolute !important;
          top: 100%;
          right: 0;
          left: auto !important;
          z-index: 11;
      }

            .vega-embed details[title="Click to view actions"] > summary svg {
                    width: 16px !important;
                    height: 16px !important;
            }
'''

VEGA_ACTIONS_MENU_JS = '''
        (function() {
            function pinVegaActions() {
                document.querySelectorAll('.vega-embed').forEach((embed) => {
                    embed.style.display = 'block';
                    embed.style.position = 'relative';

                    const details = embed.querySelector('details[title="Click to view actions"], details');
                    if (!details) {
                        return;
                    }

                    details.style.position = 'absolute';
                    details.style.top = '8px';
                    details.style.right = '8px';
                    details.style.left = 'auto';
                    details.style.margin = '0';
                    details.style.float = 'none';
                    details.style.zIndex = '10';

                    const actions = details.querySelector('.vega-actions');
                    if (actions) {
                        actions.style.position = 'absolute';
                        actions.style.top = '100%';
                        actions.style.right = '0';
                        actions.style.left = 'auto';
                        actions.style.zIndex = '11';
                    }
                });
            }

            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', pinVegaActions);
            } else {
                pinVegaActions();
            }

            [50, 150, 400, 900].forEach((delay) => setTimeout(pinVegaActions, delay));
        })();
'''


def get_embed_options(renderer="svg"):
    return {
        "renderer": renderer,
        "actions": dict(VEGA_ACTIONS),
    }


def ensure_actions_menu_inside_chart(file):
  with open(file, 'r', encoding='utf-8') as f:
    soup = BeautifulSoup(f, 'html.parser')

  style_tag = soup.find('style')
  if not style_tag:
      style_tag = soup.new_tag('style')
      soup.head.append(style_tag)

  existing_css = style_tag.string or style_tag.get_text() or ''
  if '.vega-embed > details {' not in existing_css:
      style_tag.append(VEGA_ACTIONS_MENU_CSS)

  has_pin_script = any(
      script.string and 'pinVegaActions' in script.string
      for script in soup.find_all('script')
  )
  if not has_pin_script:
      script_tag = soup.new_tag('script')
      script_tag.string = VEGA_ACTIONS_MENU_JS
      if soup.body:
          soup.body.append(script_tag)
      else:
          soup.append(script_tag)

  with open(file, 'w', encoding='utf-8') as f:
      f.write(str(soup))

seasons = ["2021/22", "2022/23", "2023/24", "2024/25", "2025/26"]
seasons_hist = ["2016/17", "2017/18", "2018/19", "2019/20"]

pitchero_caveat = f"Using Pitchero data from 2017 to 2019/20. Manually updated records from 2021 onwards"

def hack_params_css(file, overlay=False, params=True):
        css_to_add = f'''

            body {{
                    margin: 0;
            }}
  
            .vega-embed {{
                    width: 100%;
                    height: 100%;
                    transform-origin: top left;
            }}

            @media (max-width: 768px) {{
                    .vega-embed {{
                            transform: scale(0.75);
                            width: 100%;
                            height: 100%;
                    }}
            }}

            @media (max-width: 480px) {{
                    .vega-embed {{
                            transform: scale(0.5);
                            width: 100%;
                            height: 100%;
                    }}
            }}

            .chart-wrapper {{
                    display: grid;
                    grid-template-columns: 1fr 1fr;
            }}

            .vega-bind {{
                font-family: 'Lato', sans-serif !important;
                padding: 10px;
                padding-top: 5px;
                width: min-content;
            }}
            
            .vega-bind-name {{
                font-family: 'Lato', sans-serif !important;
                font-weight: bold;
                font-size: larger;
                color: #202946; 
            }}

            .vega-bind-radio input {{
                width: 1rem;
                height: 1rem;
            }}

            .vega-bind-radio label {{
                font-family: 'Lato', sans-serif;
                display: flex;
                padding: 0.1rem;
                cursor: pointer;
                transition: all 0.3s;
                font-size: medium;
            }}

            .vega-bind-radio input:checked+label {{
                background-color: #202946;
                color: #e5e4e7;
            }}

            {VEGA_ACTIONS_MENU_CSS}
        '''

        if params:
                css_to_add += f'''
            .vega-bindings {{
            border: 2px solid black;
            background-color: #e5e4e7;
            color: #202946;
            width: fit-content;
            height: fit-content;
            position: {"static" if not overlay else "fixed; top: 1rem; right: 1rem"};
            display: "block";
            justify-content: center;
            gap: 20px;
            padding: 10px;
            font-size: large;
        }}
    '''

        with open(file, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f, 'html.parser')

        style_tag = soup.find('style')
        if not style_tag:
                style_tag = soup.new_tag('style')
                soup.head.append(style_tag)

        style_tag.append(css_to_add)

        preconnect1 = soup.new_tag("link", rel="preconnect", href="https://fonts.googleapis.com")
        preconnect2 = soup.new_tag("link", rel="preconnect", href="https://fonts.gstatic.com")
        preconnect2['crossorigin'] = ''
        soup.head.insert(0, preconnect2)
        soup.head.insert(0, preconnect1)

        soup.head.append(soup.new_tag("link", rel="stylesheet", href="https://fonts.googleapis.com/css2?family=PT+Sans+Narrow:wght@400;700&display=swap"))
        soup.head.append(soup.new_tag("link", rel="stylesheet", href="https://fonts.googleapis.com/css2?family=Lato:wght@100;300;400;700;900&display=swap"))

        for script in soup.find_all('script'):
                if script.string and 'vegaEmbed' in script.string:
                        original = script.string.strip()
                        script.clear()
                        script.append(f'document.fonts.load("400 1em \'PT Sans Narrow\'").then(function() {{\n{original}\n}});')
                        break

        script_reload = """
        document.addEventListener("DOMContentLoaded", function () {
            setTimeout(() => {
                window.dispatchEvent(new Event('resize'));
            }, 100);
        });
    """
        script_reload += VEGA_ACTIONS_MENU_JS

        script_tag = soup.find_all('script')[-1]
        script_tag.append(script_reload)

        with open(file, 'w', encoding='utf-8') as f:
                f.write(str(soup))
        print(f"Updated {file}")


# Set the default configuration for altair
def alt_theme():

    title_font="PT Sans Narrow, Helvetica Neue, Helvetica, Arial, sans-serif"
    font="Lato, sans-serif"
    
    return {
        "config": {
            "axis": {
                "labelFont": title_font,
                "titleFont": title_font,
                "labelFontSize": 13,
                "titleFontSize": 24,
                "gridColor":"#202947",
                "gridOpacity": 0.2,
            },
            "text": {
                "font": font,
            },
            # Custom bar corner radius
            "bar": {
                "cornerRadiusEnd": 5,
            },
            "header": {
                "labelFont": title_font,
                "titleFont": title_font,
                "labelFontSize": 24,
                "titleFontSize": 28,
                "labelFontWeight": "bold",
                "orient": "left",
            },
            "legend": {
                "labelFont": title_font,
                "titleFont": title_font,
                "labelFontSize": 14,
                "titleFontSize": 16,
                "titlePadding": 5,
                "fillColor": "white",
                "strokeColor": "black", 
                "padding": 10,
                "titleFontWeight": "lighter",
                "titleFontStyle": "italic",
                "titleColor": "gray",
                "offset": 10,
            },
            "title": {
                "font": title_font,
                "fontSize": 48,
                "fontWeight": "bold",
                "anchor": "start",
                "align": "center",
                "titlePadding": 20,
                "subtitlePadding": 10,
                "subtitleFontSize": 13,
                "subtitleColor": "",
                "subtitleFontStyle": "italic",
                "offset": 15,
                "color": "black",
            },
            "axisX": {
                "labelAngle": 0
            },
            "facet": {
                "title": None,
                "header": None,
                "align": {"row": "each", "column": "each"},  
            },
            "resolve": {
                "scale": {
                    "y": "independent",
                    "facet": "independent"
                }
            },
            "background": "#f2f1f4",
            "scale": {
                "offsetBandPaddingOuter": 0.2,
                "offsetBandPaddingInner": 0.1,
            }
        }
    }

alt.themes.register("my_custom_theme", alt_theme)
alt.themes.enable("my_custom_theme")

game_type_scale = alt.Scale(
    domain=["League", "Cup", "Friendly", "NA"],
    range=["#202947", "#981515", "#146f14", "#20294780"]                
)

squad_scale = alt.Scale(
    domain=["1st", "2nd"],
    range=["#202947", "#146f14"]
)

def squad_row(squad, **kwargs):
    row = alt.Row(
        'Squad:N', 
        header=alt.Header(title=None, labelExpr="datum.value + ' XV'", labelFontSize=40, labels=squad==0),
        sort=alt.SortOrder('ascending'),
        **kwargs
    )
    return row

def season_column(season, **kwargs):
    column = alt.Column(
        'Season:N',
        header=alt.Header(title=None, labelFontSize=40, labels=season is None),
        sort=alt.SortOrder('ascending'),
        **kwargs
    )
    return column

position_order = ["Prop", "Hooker", "Second Row", "Back Row", "Scrum Half", "Fly Half", "Centre", "Back Three"]
