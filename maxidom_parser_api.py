import asyncio
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from models import Product
from database import AsyncSessionLocal, init_db  # Make sure `init_db` is imported
from pydantic import BaseModel
from selenium import webdriver
from bs4 import BeautifulSoup

app = FastAPI()

class ProductCreate(BaseModel):
    name: str
    price: float

class ProductResponse(ProductCreate):
    id: int

    class Config:
        orm_mode = True

# Asynchronous database session dependency
async def get_session() -> AsyncSession: # type: ignore
    async with AsyncSessionLocal() as session:
        yield session

SessionDep = Depends(get_session)

# Endpoint for fetching all products
@app.get("/products/", response_model=list[ProductResponse])
async def get_products(db: AsyncSession = SessionDep):
    result = await db.execute(select(Product))
    products = result.scalars().all()
    return products

# Endpoint for fetching a single product by ID
@app.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(product_id: int, db: AsyncSession = SessionDep):
    result = await db.execute(select(Product).filter(Product.id == product_id))
    product = result.scalars().first()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

# Endpoint for creating a new product
@app.post("/products/", response_model=ProductResponse)
async def create_product(product: ProductCreate, db: AsyncSession = SessionDep):
    new_product = Product(name=product.name, price=product.price)
    db.add(new_product)
    await db.commit()
    await db.refresh(new_product)
    return new_product

# Endpoint for updating an existing product
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

# Endpoint for deleting a product
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
        products_data = await find_products(page_url)  # Use await here
        async with AsyncSessionLocal() as db:
            for product, price in products_data:
                new_product = Product(name=product, price=float(price))
                db.add(new_product)
            await db.commit()  # Commit the changes asynchronously

    driver.quit()

# On startup, create database tables and start the scraping task
@app.on_event("startup")
async def startup_event():
    await init_db()  # Create tables at startup
    # Start the parsing task
    asyncio.create_task(parse_and_store_products())
