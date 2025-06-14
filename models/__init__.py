# This file makes the models directory a Python package
# Import and re-export all models from the main models.py file

# Import the models_helper module which already has all models imported
from models_helper import (
    db, BOM, BOMDetail, Item, Inventory, InventoryTransaction, Warehouse,
    Category, Supplier, SupplierItem, PurchaseOrder, PurchaseOrderDetail,
    SalesOrder, SalesOrderDetail, Customer, Shipment, ShipmentDetail,
    Vehicle, VehicleStorage, ShipmentOrder, DeliveryRoute, RouteStop,
    ShipmentTracking, vehicle_status_enum, shipment_status_enum, route_status_enum,
    User, Role, Permission, RolePermission, SystemSettings, Document,
    ProductionRun, ProductionRunDetail, ProductPackaging, PackagingMaterial,
    DemandForecast, InventoryReplenishmentPlan, EmployeeShift, ProductionEfficiency,
    CustomerInteraction, DiscountPromotion, SalesReturn, SupplierLedgerEntry, ItemCostHistory,
    SupplierPayment, QualityCheck, QualityCheckResult, QCParameter, Equipment,
    MaintenanceLog, WarehouseSection, WarehouseSlot, Batch, BatchSlot,
    ProductionOrder, ProductionLine, ProductionStep, ProductionStepRecord,
    ProductionParameter, ProductionProcess, QualityInspection, QualityInspectionCriteria,
    AgingRecord, SupportTicket, TicketResponse, QCTest, QCTestResult,
    PackagingOrder, PackagingLine, PackagingMaterialUsage, ProductLabel,
    SalesRepresentative, SalesInvoice, SalesPayment, SalesActivityLog,
    SalesReturnItem, CashAccount, CashTransaction, CashTransferVoucher, CashReconciliation,
    RepresentativeRoute, CustomerVisit, RepresentativePerformance, VisitPhoto,
    WorkerProductivity,AISuggestion,
)

# Re-export all imported models
__all__ = [
    'db', 'BOM', 'BOMDetail', 'Item', 'Inventory', 'InventoryTransaction', 'Warehouse',
    'Category', 'Supplier', 'SupplierItem', 'PurchaseOrder', 'PurchaseOrderDetail',
    'SalesOrder', 'SalesOrderDetail', 'Customer', 'Shipment', 'ShipmentDetail',
    'Vehicle', 'VehicleStorage', 'ShipmentOrder', 'DeliveryRoute', 'RouteStop',
    'ShipmentTracking', 'vehicle_status_enum', 'shipment_status_enum', 'route_status_enum',
    'User', 'Role', 'Permission', 'RolePermission', 'SystemSettings', 'Document',
    'ProductionRun', 'ProductionRunDetail', 'ProductPackaging', 'PackagingMaterial',
    'DemandForecast', 'InventoryReplenishmentPlan', 'EmployeeShift', 'ProductionEfficiency',
    'CustomerInteraction', 'DiscountPromotion', 'SalesReturn', 'SupplierLedgerEntry',
    'SupplierPayment', 'QualityCheck', 'QualityCheckResult', 'QCParameter', 'Equipment',
    'MaintenanceLog', 'WarehouseSection', 'WarehouseSlot', 'Batch', 'BatchSlot',
    'ProductionOrder', 'ProductionLine', 'ProductionStep', 'ProductionStepRecord',
    'ProductionParameter', 'ProductionProcess', 'QualityInspection', 'QualityInspectionCriteria',
    'AgingRecord', 'SupportTicket', 'TicketResponse', 'QCTest', 'QCTestResult',
    'PackagingOrder', 'PackagingLine', 'PackagingMaterialUsage', 'ProductLabel',
    'SalesRepresentative', 'SalesInvoice', 'SalesPayment', 'SalesActivityLog',
    'SalesReturnItem', 'CashAccount', 'CashTransaction', 'CashTransferVoucher', 'CashReconciliation',
    'RepresentativeRoute', 'CustomerVisit', 'RepresentativePerformance', 'VisitPhoto',
    'WorkerProductivity','AISuggestion'
]
