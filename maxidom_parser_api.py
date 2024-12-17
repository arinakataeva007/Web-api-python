import asyncio
from fastapi import Depends, FastAPI, HTTPException, WebSocket
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from database import AsyncSessionLocal, init_db, Product
from pydantic import BaseModel
from selenium import webdriver
from bs4 import BeautifulSoup
from starlette.websockets import WebSocketDisconnect
import json

app = FastAPI()

class ProductCreate(BaseModel):
    name: str
    price: float

class ProductResponse(ProductCreate):
    id: int

    class Config:
        orm_mode = True

async def get_session() -> AsyncSession: # type: ignore
    async with AsyncSessionLocal() as session:
        yield session

SessionDep = Depends(get_session)

# создаем объект, который будет хранить все подключения
class ConnectionManager:
    def __init__(self):
        self.connsections: list[WebSocket] = [] # список соединений по вебсокетам

    async def connect(self, websocket: WebSocket):
        await websocket.accept() # говорим клиенту, что готовы работать с ним, устанавливаем соединение
        self.connsections.append(websocket) # добавляем соединение в список
    async def broadcast(self, data: str): # обходит список подключений и каждому подключению отправляет
        for conn in self.connsections:
            await conn.send_text(data)

manager = ConnectionManager()

# эндпоинт на получение всех товаров
@app.get("/products/", response_model=list[ProductResponse])
async def get_products(db: AsyncSession = SessionDep):
    result = await db.execute(select(Product))
    products = result.scalars().all()
    return products

# эндпоинт на подучение товара по id
@app.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(product_id: int, db: AsyncSession = SessionDep):
    result = await db.execute(select(Product).filter(Product.id == product_id))
    product = result.scalars().first()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

# эндпоинт на создание продукта
@app.post("/products/", response_model=ProductResponse)
async def create_product(product: ProductCreate, db: AsyncSession = SessionDep):
    new_product = Product(name=product.name, price=product.price)
    db.add(new_product)
    await db.commit()
    await db.refresh(new_product)
    await manager.broadcast(json.dumps({"id": new_product.id, "name": new_product.name, "price": new_product.price}))
    return new_product

# эндпоинт на обновление данных продукта
@app.put("/products/{product_id}", response_model=ProductResponse)
async def update_product(product_id: int, product: ProductCreate, db: AsyncSession = SessionDep):
    result = await db.execute(select(Product).filter(Product.id == product_id))
    db_product = result.scalars().first()
    if db_product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    
    db_product.name = product.name
    db_product.price = product.price
    await db.commit()
    await db.refresh(db_product)
    return db_product

# эндпоинт на удаление продукта из базы
@app.delete("/products/{product_id}")
async def delete_product(product_id: int, db: AsyncSession = SessionDep):
    result = await db.execute(select(Product).filter(Product.id == product_id))
    db_product = result.scalars().first()
    if db_product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    
    await db.delete(db_product)
    await db.commit()
    return {"message": "Product deleted successfully"}

# Scraping function to fetch and store products
async def parse_and_store_products():
    driver = webdriver.Chrome()
    driver.get('https://www.maxidom.ru/catalog/potolki/')
    await asyncio.sleep(5)

    async def find_products(page):
        driver.get(page)
        await asyncio.sleep(5)
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
        print(f"Parsing page: {links['href']}")
        products_data = await find_products(page_url) 
        async with AsyncSessionLocal() as db:
            for product, price in products_data:
                new_product = Product(name=product, price=float(price))
                db.add(new_product)
            await db.commit()

    driver.quit()

@app.on_event("startup")
async def startup_event():
    await init_db()  
    asyncio.create_task(parse_and_store_products())

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, db: AsyncSession = Depends(get_session)):
    await manager.connect(websocket) 
    try:
        while True:  
            data = await websocket.receive_text()
            print(f"Received data: {data}")

            if data.startswith("get_product:"):
                try:
                    product_id = int(data.split(":")[1])
                    result = await db.execute(select(Product).filter(Product.id == product_id))
                    product = result.scalars().first()

                    if product:
                        await websocket.send_json({
                            "id": product.id,
                            "name": product.name,
                            "price": product.price
                        })
                    else:
                        await websocket.send_json({"error": "Product not found"})
                except (ValueError, IndexError):
                    await websocket.send_json({"error": "Invalid product request format"})
            else:
                await websocket.send_text(data * 10)
    except WebSocketDisconnect:
        print("Client disconnected")
