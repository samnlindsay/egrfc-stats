import altair as alt
from bs4 import BeautifulSoup

seasons = ["2021/22", "2022/23", "2023/24", "2024/25", "2025/26"]
seasons_hist = ["2016/17", "2017/18", "2018/19", "2019/20"]

pitchero_caveat = f"Using Pitchero data from 2017 to 2019/20. Manually updated records from 2021 onwards"

def hack_params_css(file, overlay=False, params=True):

  # Define the CSS to be added
  css_to_add = f'''

      body {{
          margin: 0;
      }}
  
      /* Default size for larger screens */
      .vega-embed {{
          width: 100%;
          height: 100%;
          transform-origin: top left;
      }}

      /* Scale for tablet devices */
      @media (max-width: 768px) {{
          .vega-embed {{
              transform: scale(0.75);
              width: 100%;
              height: 100%;
          }}
      }}

      /* Scale for mobile devices */
      @media (max-width: 480px) {{
          .vega-embed {{
              transform: scale(0.5);
              width: 100%;
              height: 100%;
          }}
      }}

      .chart-wrapper {{
          display: grid;
          grid-template-columns: 1fr 1fr; /* Chart takes 3x space, form takes 1x */
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

  # Read the file content using BeautifulSoup
  with open(file, 'r', encoding='utf-8') as f:
    soup = BeautifulSoup(f, 'html.parser')

  # Find the <style> tag or create it if it doesn't exist
  style_tag = soup.find('style')
  if not style_tag:
      style_tag = soup.new_tag('style')
      soup.head.append(style_tag)

  # Append the new CSS to the <style> tag
  style_tag.append(css_to_add)

  # Add google fonts
  soup.head.append(soup.new_tag("link", rel="stylesheet", href="https://fonts.googleapis.com/css?family=PT+Sans+Narrow:400,700"))
  soup.head.append(soup.new_tag("link", rel="stylesheet", href="https://fonts.googleapis.com/css?family=Lato:100,300,400,700,900"))     

  script_reload = """
    document.addEventListener("DOMContentLoaded", function () {
      setTimeout(() => {
        window.dispatchEvent(new Event('resize'));
      }, 100);
    });
  """     
  # Add script_reload to the last script tag in document
  script_tag = soup.find_all('script')[-1]
  script_tag.append(script_reload)
  
  # Write the modified HTML back to the file
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
                "labelFont": font,
                "titleFont": title_font,
                "labelFontSize": 13,
                "titleFontSize": 24,
                "gridColor":"#202947",
                "gridOpacity": 0.2,
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
                "labelFont": font,
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
            "background": "#f2f1f4"
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
