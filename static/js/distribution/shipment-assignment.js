// Define the shipmentAssignmentApp function for Alpine.js
function shipmentAssignmentApp() {
    return {
        orders: [],
        selectedOrder: null,
        orderSearch: '',
        shipmentForm: {
            vehicle_id: '',
            carrier_name: 'التوصيل الداخلي',
            estimated_delivery_date: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString().split('T')[0],
            notes: ''
        },
        init: function() {
            console.log("Initializing shipment assignment app");
            this.loadOrders();
        },
        loadOrders: function() {
            // This will be populated from the template
            console.log("Loading orders");
            this.orders = window.pendingOrdersData || [];
            console.log("Loaded orders:", this.orders);
        },
        get filteredOrders() {
            if (!this.orderSearch) return this.orders;
            var search = this.orderSearch.toLowerCase();
            return this.orders.filter(function(order) {
                return order.id.toString().includes(search) ||
                    (order.customer_name && order.customer_name.toLowerCase().includes(search));
            });
        },
        selectOrder: function(order) {
            console.log("Selecting order:", order);
            this.selectedOrder = order;
        },
        formatDate: function(dateString) {
            if (!dateString) return '-';
            var date = new Date(dateString);
            return date.toLocaleDateString('ar-EG');
        },
        formatCurrency: function(amount) {
            return new Intl.NumberFormat('ar-EG', {
                style: 'currency',
                currency: 'EGP'
            }).format(amount || 0);
        },
        assignShipment: function() {
            var self = this;
            if (!this.selectedOrder || !this.shipmentForm.vehicle_id) {
                window.showToast('يرجى اختيار طلب مبيعات ومركبة', 'error');
                return;
            }

            console.log("Assigning shipment:", {
                order: this.selectedOrder,
                form: this.shipmentForm
            });

            var shipmentData = {
                sales_order_id: this.selectedOrder.id,
                vehicle_id: this.shipmentForm.vehicle_id,
                carrier_name: this.shipmentForm.carrier_name,
                estimated_delivery_date: this.shipmentForm.estimated_delivery_date,
                notes: this.shipmentForm.notes
            };

            fetch('/distribution/api/shipments/assign', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(shipmentData)
                })
                .then(function(response) {
                    return response.json();
                })
                .then(function(data) {
                    if (data.success) {
                        // Check capacity utilization and show warnings if needed
                        if (data.vehicle_capacity) {
                            const weightUtil = data.vehicle_capacity.weight_utilization;
                            const volumeUtil = data.vehicle_capacity.volume_utilization;

                            // Show success message
                            window.showToast('تم تعيين الشحنة بنجاح', 'success');

                            // Show capacity warnings if utilization is high (over 80%)
                            if (weightUtil > 80) {
                                setTimeout(function() {
                                    window.showToast(`تحذير: استخدام السعة (الوزن) مرتفع: ${Math.round(weightUtil)}%`, 'warning');
                                }, 500);
                            }

                            if (volumeUtil > 80) {
                                setTimeout(function() {
                                    window.showToast(`تحذير: استخدام السعة (الحجم) مرتفع: ${Math.round(volumeUtil)}%`, 'warning');
                                }, 1000);
                            }
                        } else {
                            window.showToast('تم تعيين الشحنة بنجاح', 'success');
                        }

                        // Redirect to shipments page after a short delay to allow seeing the warnings
                        setTimeout(function() {
                            window.location.href = '/distribution/shipments';
                        }, 2000);
                    } else {
                        window.showToast(data.message || 'حدث خطأ أثناء تعيين الشحنة', 'error');
                    }
                })
                .catch(function(error) {
                    console.error('Error assigning shipment:', error);
                    window.showToast('حدث خطأ أثناء تعيين الشحنة', 'error');
                });
        }
    };
}

// Global toast notification function
window.showToast = function(message, type) {
    // Check if we have a toast container
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'fixed bottom-4 right-4 z-50 flex flex-col space-y-2';
        document.body.appendChild(container);
    }

    // Create toast element
    const toast = document.createElement('div');
    toast.className = "px-4 py-3 rounded-lg shadow-lg text-white flex items-center transition-all duration-300 transform translate-x-full opacity-0";

    // Set background color based on type
    if (type === 'success') {
        toast.classList.add('bg-green-600');
    } else if (type === 'error') {
        toast.classList.add('bg-red-600');
    } else if (type === 'warning') {
        toast.classList.add('bg-yellow-600');
    } else {
        toast.classList.add('bg-blue-600');
    }

    // Add icon based on type
    let icon = '';
    if (type === 'success') {
        icon = '<i class="fas fa-check-circle ml-2"></i>';
    } else if (type === 'error') {
        icon = '<i class="fas fa-exclamation-circle ml-2"></i>';
    } else if (type === 'warning') {
        icon = '<i class="fas fa-exclamation-triangle ml-2"></i>';
    } else {
        icon = '<i class="fas fa-info-circle ml-2"></i>';
    }

    toast.innerHTML = icon + '<span>' + message + '</span>';
    container.appendChild(toast);

    // Animate in
    setTimeout(function() {
        toast.classList.remove('translate-x-full', 'opacity-0');
    }, 10);

    // Remove after 5 seconds
    setTimeout(function() {
        toast.classList.add('translate-x-full', 'opacity-0');
        setTimeout(function() {
            container.removeChild(toast);
        }, 300);
    }, 5000);
};