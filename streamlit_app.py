import streamlit as st
import datetime
import requests
import json
import pandas as pd
from retry import retry


def get_catalogs_wb() -> dict:
    """получаем полный каталог Wildberries"""
    url = 'https://static-basket-01.wbbasket.ru/vol0/data/main-menu-ru-ru-v3.json'
    headers = {'Accept': '*/*', 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    return requests.get(url, headers=headers).json()


def get_data_category(catalogs_wb: dict) -> list:
    """сбор данных категорий из каталога Wildberries"""
    catalog_data = []
    stack = [catalogs_wb]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            catalog_data.append({
                'name': item.get('name', ''),
                'shard': item.get('shard', None),
                'url': item.get('url', ''),
                'query': item.get('query', None)
            })
            if 'childs' in item:
                stack.extend(item['childs'])
        elif isinstance(item, list):
            stack.extend(item)
    return catalog_data


def search_category_in_catalog(url: str, catalog_list: list) -> dict:
    """проверка пользовательской ссылки на наличии в каталоге"""
    for catalog in catalog_list:
        if catalog['url'] == url.split('https://www.wildberries.ru')[-1]:
            print(f'найдено совпадение: {catalog["name"]}')
            return catalog


def get_data_from_json(json_file: dict) -> list:
    data_list = []
    products = json_file.get('data', {}).get('products', [])
    if not products:
        logging.warning('Внимание: нет данных для обработки.')
    for product in products:
        data_list.append({
            'id': product.get('id'),
            'name': product.get('name'),
            'price': int(product.get('priceU', 0) / 100),
            'salePriceU': int(product.get('salePriceU', 0) / 100),
            'cashback': product.get('feedbackPoints'),
            'sale': product.get('sale'),
            'brand': product.get('brand'),
            'rating': product.get('rating'),
            'supplier': product.get('supplier'),
            'supplierRating': product.get('supplierRating'),
            'feedbacks': product.get('feedbacks'),
            'reviewRating': product.get('reviewRating'),
            'promoTextCard': product.get('promoTextCard'),
            'promoTextCat': product.get('promoTextCat'),
            'link': f'https://www.wildberries.ru/catalog/{product.get("id")}/detail.aspx?targetUrl=BP'
        })
    return data_list


@retry(Exception, tries=5, delay=2)
def scrap_page(page: int, shard: str, query: str, low_price: int, top_price: int, discount: int = None) -> dict:
    """Сбор данных со страниц"""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0)"}
    url = f'https://catalog.wb.ru/catalog/{shard}/catalog?appType=1&curr=rub' \
          f'&dest=-1257786' \
          f'&locale=ru' \
          f'&page={page}' \
          f'&priceU={low_price * 100};{top_price * 100}' \
          f'&sort=popular&spp=0' \
          f'&{query}' \
          f'&discount={discount}'
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        print(f'Ошибка HTTP: {r.status_code}')
        raise Exception(f'Ошибка HTTP: {r.status_code}')
    print(f'Статус: {r.status_code} Страница {page} Идет сбор...')
    return r.json()

def parser(url: str, low_price: int = 1, top_price: int = 1000000, discount: int = 0):
    """основная функция"""
    # получаем данные по заданному каталогу
    catalog_data = get_data_category(get_catalogs_wb())
    try:
        # поиск введенной категории в общем каталоге
        category = search_category_in_catalog(url=url, catalog_list=catalog_data)
        data_list = []
        for page in range(1, 51):  # вб отдает 50 страниц товара (раньше было 100)
            data = scrap_page(
                page=page,
                shard=category['shard'],
                query=category['query'],
                low_price=low_price,
                top_price=top_price,
                discount=discount)
            print(f'Добавлено позиций: {len(get_data_from_json(data))}')
            if len(get_data_from_json(data)) > 0:
                data_list.extend(get_data_from_json(data))
            else:
                break
        
        if not data_list:
            print('Внимание: нет данных для сохранения.')
            return
        
        return data_list
    except TypeError:
        print('Ошибка! Возможно не верно указан раздел. Удалите все доп фильтры с ссылки')
    except PermissionError:
        print('Ошибка! Вы забыли закрыть созданный ранее excel файл. Закройте и повторите попытку')
    except KeyError:
        print('Ошибка! Не найдены ключи в данных категории.')
    except Exception as e:
        print(f'Неизвестная ошибка: {e}')

df = None
st.set_page_config(layout="wide", page_icon='⚡', page_title="Parser Wildberries")

with st.sidebar:
    url = st.text_input(label="Вставьте ссылку", placeholder="https://www.wildberries.ru/catalog/muzhchinam/bele", help="Ссылка на каталог Wildberries")
    low_price = st.number_input(label="Минимальная цена", min_value=1, max_value=1000000, value=300)
    top_price = st.number_input(label="Максимальная цена", min_value=1, max_value=1000000, value=900)
    discount = st.slider("Скидка", 0, 100, value=0, help="0 - без скидки")

with st.sidebar:
    st.markdown('''Задайте категорию, задайте нужные цены, цена без скидки  - 0''', unsafe_allow_html=True)

##############################################################################################################

st.title('Parser Wildberries!⚡')

ui_container = st.container()
with ui_container:
    submit = st.button(label='Получить данные')

# if user input is empty and button is clicked then show warning
if submit and url == "":
    with ui_container:
        st.warning("Укажите ссылку на каталог")

# if user input is not empty and button is clicked then generate slides
elif submit:
    with ui_container:
        with st.spinner('Загрузка ...⏳'):

            try:
                data = parser(url=url, low_price=low_price, top_price=top_price, discount=discount)
                df = pd.DataFrame(data)
                st.table(df)
            except:
                    pass
                
                