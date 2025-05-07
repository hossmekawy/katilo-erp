"""
Helper module to import models from models.py
This avoids circular imports and issues with the models directory
"""

import os
import importlib.util

# Get the absolute path to the models.py file
current_dir = os.path.dirname(os.path.abspath(__file__))
models_path = os.path.join(current_dir, 'models.py')
print(f"Looking for models.py at: {models_path}")
if not os.path.exists(models_path):
    print(f"ERROR: models.py not found at {models_path}")
    # Try to find models.py in parent directory
    parent_dir = os.path.dirname(current_dir)
    models_path = os.path.join(parent_dir, 'models.py')
    print(f"Trying parent directory: {models_path}")
    if not os.path.exists(models_path):
        print(f"ERROR: models.py not found at {models_path} either")

# Import the models.py file as a module
spec = importlib.util.spec_from_file_location('models_module', models_path)
models_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(models_module)

# Export all models from the module
db = models_module.db
BOM = models_module.BOM
BOMDetail = models_module.BOMDetail
Item = models_module.Item
Inventory = models_module.Inventory
InventoryTransaction = models_module.InventoryTransaction
Warehouse = models_module.Warehouse
Category = models_module.Category
Supplier = models_module.Supplier
SupplierItem = models_module.SupplierItem
ItemCostHistory = models_module.ItemCostHistory
PurchaseOrder = models_module.PurchaseOrder
PurchaseOrderDetail = models_module.PurchaseOrderDetail
SalesOrder = models_module.SalesOrder
SalesOrderDetail = models_module.SalesOrderDetail
Customer = models_module.Customer
Shipment = models_module.Shipment
ShipmentDetail = models_module.ShipmentDetail
Vehicle = models_module.Vehicle
VehicleStorage = models_module.VehicleStorage
ShipmentOrder = models_module.ShipmentOrder
DeliveryRoute = models_module.DeliveryRoute
RouteStop = models_module.RouteStop
ShipmentTracking = models_module.ShipmentTracking
vehicle_status_enum = models_module.vehicle_status_enum
shipment_status_enum = models_module.shipment_status_enum
route_status_enum = models_module.route_status_enum
User = models_module.User
Role = models_module.Role
Permission = models_module.Permission
RolePermission = models_module.RolePermission
SystemSettings = models_module.SystemSettings
Document = models_module.Document
ProductionRun = models_module.ProductionRun
ProductionRunDetail = models_module.ProductionRunDetail
ProductPackaging = models_module.ProductPackaging
PackagingMaterial = models_module.PackagingMaterial
DemandForecast = models_module.DemandForecast
InventoryReplenishmentPlan = models_module.InventoryReplenishmentPlan
EmployeeShift = models_module.EmployeeShift
ProductionEfficiency = models_module.ProductionEfficiency
CustomerInteraction = models_module.CustomerInteraction
DiscountPromotion = models_module.DiscountPromotion
SalesReturn = models_module.SalesReturn
SupplierLedgerEntry = models_module.SupplierLedgerEntry
SupplierPayment = models_module.SupplierPayment
QualityCheck = models_module.QualityCheck
QualityCheckResult = models_module.QualityCheckResult
QCParameter = models_module.QCParameter
Equipment = models_module.Equipment
MaintenanceLog = models_module.MaintenanceLog
WarehouseSection = models_module.WarehouseSection
WarehouseSlot = models_module.WarehouseSlot
Batch = models_module.Batch
BatchSlot = models_module.BatchSlot
ProductionOrder = models_module.ProductionOrder
ProductionLine = models_module.ProductionLine
ProductionStep = models_module.ProductionStep
ProductionStepRecord = models_module.ProductionStepRecord
ProductionParameter = models_module.ProductionParameter
ProductionProcess = models_module.ProductionProcess
QualityInspection = models_module.QualityInspection
QualityInspectionCriteria = models_module.QualityInspectionCriteria
AgingRecord = models_module.AgingRecord
SupportTicket = models_module.SupportTicket
TicketResponse = models_module.TicketResponse
QCTest = models_module.QCTest
QCTestResult = models_module.QCTestResult
WorkerProductivity = models_module.WorkerProductivity
PackagingOrder = models_module.PackagingOrder
PackagingLine = models_module.PackagingLine
PackagingMaterialUsage = models_module.PackagingMaterialUsage
ProductLabel = models_module.ProductLabel
SalesRepresentative = models_module.SalesRepresentative
SalesInvoice = models_module.SalesInvoice
SalesPayment = models_module.SalesPayment
SalesActivityLog = models_module.SalesActivityLog
SalesReturn = models_module.SalesReturn
SalesReturnItem = models_module.SalesReturnItem
DiscountPromotion = models_module.DiscountPromotion
CashAccount = models_module.CashAccount
CashTransaction = models_module.CashTransaction
CashTransferVoucher = models_module.CashTransferVoucher
CashReconciliation = models_module.CashReconciliation
RepresentativeRoute = models_module.RepresentativeRoute
CustomerVisit = models_module.CustomerVisit
RepresentativePerformance = models_module.RepresentativePerformance
VisitPhoto = models_module.VisitPhoto
AISuggestion = models_module.AISuggestion

