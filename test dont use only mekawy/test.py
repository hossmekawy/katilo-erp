import requests

cookies = {
    'csrftoken': '4ag3QAOedGQQREsXjgOYvEs4f0t8GQJX',
    'session': '.eJxNUe1qAyEQfJXg77TZ1dPVe5U2hPWrCZRLuPNoIeTda7xARVidmf0Y9S5O-ZuXc1rE-HEXu1I38cPzdJm-xF58rmAGfkaFzyhDY9yugU1QndCYYdhk2kA75xZTY2yfpHqqK_O7jtL_Dl7jqO-x-YBGqc7sy2abrVyTtTg-jvt66TktZzGWeU0VXaIYBTibNaDnOKC0MaeUI3vKyhPGEFkPGoMFGwwCuAzENmmyNT8ojFyLsrcawTBKBQYTaWPA1y40IEgnc6VQUcwhyOSCJ0jsnCEOiQlife7TuqR5c4MVTum3_oc4l3IbDweU9A514agB4BCuU-FQ3pb1drvORTz-AIMbguI.Z_OlzQ.29In8dDOM3VrQegTEmMhj6uLuPw',
}

headers = {
    'Accept': '*/*',
    'Accept-Language': 'en-US,en;q=0.9,ar;q=0.8',
    'Connection': 'keep-alive',
    'Content-Type': 'application/json',
    'Referer': 'http://127.0.0.1:5000/dashboard',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-GPC': '1',
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
    'X-Requested-With': 'XMLHttpRequest',
    # 'Cookie': 'csrftoken=4ag3QAOedGQQREsXjgOYvEs4f0t8GQJX; session=.eJxNUe1qAyEQfJXg77TZ1dPVe5U2hPWrCZRLuPNoIeTda7xARVidmf0Y9S5O-ZuXc1rE-HEXu1I38cPzdJm-xF58rmAGfkaFzyhDY9yugU1QndCYYdhk2kA75xZTY2yfpHqqK_O7jtL_Dl7jqO-x-YBGqc7sy2abrVyTtTg-jvt66TktZzGWeU0VXaIYBTibNaDnOKC0MaeUI3vKyhPGEFkPGoMFGwwCuAzENmmyNT8ojFyLsrcawTBKBQYTaWPA1y40IEgnc6VQUcwhyOSCJ0jsnCEOiQlife7TuqR5c4MVTum3_oc4l3IbDweU9A514agB4BCuU-FQ3pb1drvORTz-AIMbguI.Z_OlzQ.29In8dDOM3VrQegTEmMhj6uLuPw',
}

response = requests.get('https://katilo.pythonanywhere.com/api/categories', cookies=cookies, headers=headers)
response.json()