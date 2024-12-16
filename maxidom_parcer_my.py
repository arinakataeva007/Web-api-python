from selenium import webdriver
from selenium.webdriver.common.by import By 
from bs4 import BeautifulSoup 
import time 

driver = webdriver.Chrome()
driver.get('https://www.maxidom.ru/catalog/potolki/')
time.sleep(5)

def find_products(page):
  driver.get(page)
  time.sleep(5)
  html = driver.page_source
  soup_product = BeautifulSoup(html, "lxml")
  products = soup_product.find_all("div", class_="col-12")
  product_list = [] 
  for product in products:
    articles = product.find_all("article")
    for article in articles:
      a_tags = article.find_all("a", {"data-v-32495050": True})
      price_tag = article.find_all("div", {"data-repid-price": True})
      for price in price_tag:
        price1 = price["data-repid-price"]
      for a in a_tags:
        if a.get('title') is not None and a.get('href') != '#':
          product_list.append((a.get('title'), price1)) 
  return product_list

html = driver.page_source
soup = BeautifulSoup(html, "lxml")
next_page = soup.find("div", class_="lvl2__content-nav-numbers-number")
links_pages = next_page.find_all("a", href=True)

for links in links_pages:
  if links['href'] == '#':
    page_url = "https://www.maxidom.ru/catalog/potolki/"
  else:
    page_url = f"https://www.maxidom.ru{links['href']}"
  print(f"Вывод для {links['href']}")
  products_data = find_products(page_url)
  for product, price in products_data:
    print(f"Товар: {product}, Цена: {price}")

driver.quit()