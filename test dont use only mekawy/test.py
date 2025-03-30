from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import func
from sqlalchemy import event

db = SQLAlchemy()

class Warehouse(db.Model):
    __tablename__ = 'warehouses'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=func.now())
    
    # Relationships
    inventory_locations = db.relationship('InventoryLocation', backref='warehouse', lazy=True)
    storage_condition_logs = db.relationship('StorageConditionLog', backref='warehouse', lazy=True)

class InventoryLocation(db.Model):
    __tablename__ = 'inventory_locations'
    
    id = db.Column(db.Integer, primary_key=True)
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=func.now())
    
    # Relationships
    count_items = db.relationship('CountItem', backref='inventory_location', lazy=True)

class Item(db.Model):
    __tablename__ = 'items'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    item_type = db.Column(db.Enum('raw_material', 'intermediate_item', 'package', 'finished_product', name='item_type_enum'), nullable=False)
    created_at = db.Column(db.DateTime, default=func.now())
    
    # Relationships
    count_items = db.relationship('CountItem', backref='item', lazy=True)

@event.listens_for(Item, 'after_insert')
def copy_item_to_raw_material(mapper, connection, target):
    if target.item_type == 'raw_material':
        raw_material = RawMaterial(
            name=target.name,
            description=target.description,
            quantity=0,  # Initialize with zero quantity or as needed
            unit='unit'  # Set a default unit or as needed
        )
        db.session.add(raw_material)
        db.session.commit()

class InventoryCount(db.Model):
    __tablename__ = 'inventory_counts'
    
    id = db.Column(db.Integer, primary_key=True)
    count_number = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=func.now())
    
    # Relationships
    count_items = db.relationship('CountItem', backref='inventory_count', lazy=True)

class CountItem(db.Model):
    __tablename__ = 'count_items'
    
    id = db.Column(db.Integer, primary_key=True)
    count_id = db.Column(db.Integer, db.ForeignKey('inventory_counts.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey('inventory_locations.id'), nullable=False)
    batch_number = db.Column(db.String(50))
    lot_number = db.Column(db.String(50))
    quantity = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=func.now())
    
    __table_args__ = (
        db.UniqueConstraint('count_id', 'item_id', 'location_id', 'batch_number', 'lot_number',
                            name='uix_count_item_location_batch_lot'),
    )
    
    def __repr__(self):
        return f'<CountItem {self.inventory_count.count_number} - {self.item.name}>'

class StorageConditionLog(db.Model):
    __tablename__ = 'storage_condition_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey('inventory_locations.id'))
    temperature = db.Column(db.Float)  # Temperature in Celsius
    humidity = db.Column(db.Float)  # Humidity percentage
    recorded_at = db.Column(db.DateTime, default=func.now())
    status = db.Column(db.String(20), default='normal')  # normal, warning, critical
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=func.now())
    
    # Relationships
    location = db.relationship('InventoryLocation')

class RawMaterial(db.Model):
    __tablename__ = 'raw_materials'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    quantity = db.Column(db.Float, nullable=False)  # Quantity in stock
    unit = db.Column(db.String(20), nullable=False)  # Unit of measurement (e.g., kg, liters)
    created_at = db.Column(db.DateTime, default=func.now())
    
    # Relationships
    recipe_ingredients = db.relationship('RecipeIngredient', backref='raw_material', lazy=True)

class Recipe(db.Model):
    __tablename__ = 'recipes'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    product_type = db.Column(db.Enum('dairy', 'cheese', name='product_type_enum'), nullable=False)
    created_at = db.Column(db.DateTime, default=func.now())
    
    # Relationships
    ingredients = db.relationship('RecipeIngredient', backref='recipe', lazy=True)

class RecipeIngredient(db.Model):
    __tablename__ = 'recipe_ingredients'
    
    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipes.id'), nullable=False)
    raw_material_id = db.Column(db.Integer, db.ForeignKey('raw_materials.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False)  # Quantity required for the recipe
    unit = db.Column(db.String(20), nullable=False)  # Unit of measurement (e.g., kg, liters)
    created_at = db.Column(db.DateTime, default=func.now())
    
    def __repr__(self):
        return f'<RecipeIngredient {self.recipe.name} - {self.raw_material.name}>'