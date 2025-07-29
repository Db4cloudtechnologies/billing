import requests
import sys
from datetime import datetime, date
import json

class BillingSystemAPITester:
    def __init__(self, base_url="https://4adbbd9a-92c4-43ba-af81-feca90bf120e.preview.emergentagent.com/api"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.created_document_id = None
        self.created_item_id = None

    def run_test(self, name, method, endpoint, expected_status, data=None, params=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}" if endpoint else self.base_url
        headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    response_data = response.json()
                    if isinstance(response_data, dict) and len(str(response_data)) < 500:
                        print(f"   Response: {response_data}")
                    return True, response_data
                except:
                    return True, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   Error: {error_data}")
                except:
                    print(f"   Error: {response.text}")
                return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_root_endpoint(self):
        """Test root API endpoint"""
        success, response = self.run_test(
            "Root API Endpoint",
            "GET",
            "",
            200
        )
        return success

    def test_dashboard_stats(self):
        """Test dashboard statistics endpoint"""
        success, response = self.run_test(
            "Dashboard Statistics",
            "GET",
            "dashboard/stats",
            200
        )
        if success:
            expected_keys = ['total_documents', 'status_counts', 'type_counts', 'total_amount']
            for key in expected_keys:
                if key not in response:
                    print(f"⚠️  Warning: Missing key '{key}' in stats response")
        return success

    def test_create_document(self):
        """Test creating a billing document"""
        test_data = {
            "billing_type": "Standard invoice",
            "billing_date": date.today().isoformat(),
            "customer_name": "Test Customer",
            "customer_email": "test@example.com",
            "customer_address": "123 Test Street, Test City",
            "notes": "Test document created by automated test"
        }
        
        success, response = self.run_test(
            "Create Billing Document",
            "POST",
            "billing-documents",
            200,
            data=test_data
        )
        
        if success and 'id' in response:
            self.created_document_id = response['id']
            print(f"   Created document ID: {self.created_document_id}")
            
            # Verify required fields
            required_fields = ['id', 'document_number', 'billing_type', 'status']
            for field in required_fields:
                if field not in response:
                    print(f"⚠️  Warning: Missing field '{field}' in document response")
        
        return success

    def test_get_documents(self):
        """Test getting all documents"""
        success, response = self.run_test(
            "Get All Documents",
            "GET",
            "billing-documents",
            200
        )
        
        if success:
            if isinstance(response, list):
                print(f"   Found {len(response)} documents")
            else:
                print("⚠️  Warning: Response is not a list")
        
        return success

    def test_get_single_document(self):
        """Test getting a specific document"""
        if not self.created_document_id:
            print("⚠️  Skipping - No document ID available")
            return True
            
        success, response = self.run_test(
            "Get Single Document",
            "GET",
            f"billing-documents/{self.created_document_id}",
            200
        )
        return success

    def test_update_document(self):
        """Test updating a document"""
        if not self.created_document_id:
            print("⚠️  Skipping - No document ID available")
            return True
            
        update_data = {
            "customer_name": "Updated Test Customer",
            "notes": "Updated by automated test"
        }
        
        success, response = self.run_test(
            "Update Document",
            "PUT",
            f"billing-documents/{self.created_document_id}",
            200,
            data=update_data
        )
        return success

    def test_add_item_to_document(self):
        """Test adding an item to a document"""
        if not self.created_document_id:
            print("⚠️  Skipping - No document ID available")
            return True
            
        item_data = {
            "item_name": "Test Product",
            "description": "A test product for automated testing",
            "category": "Product",
            "quantity": 2.0,
            "unit_price": 50.00,
            "tax_rate": 10.0
        }
        
        success, response = self.run_test(
            "Add Item to Document",
            "POST",
            f"billing-documents/{self.created_document_id}/items",
            200,
            data=item_data
        )
        
        if success and 'items' in response and len(response['items']) > 0:
            self.created_item_id = response['items'][-1]['id']
            print(f"   Created item ID: {self.created_item_id}")
            
            # Verify calculations
            item = response['items'][-1]
            expected_total = item['quantity'] * item['unit_price']
            expected_tax = expected_total * (item['tax_rate'] / 100)
            
            if abs(item['total_price'] - expected_total) > 0.01:
                print(f"⚠️  Warning: Total price calculation incorrect")
            if abs(item['tax_amount'] - expected_tax) > 0.01:
                print(f"⚠️  Warning: Tax amount calculation incorrect")
        
        return success

    def test_update_item(self):
        """Test updating an item in a document"""
        if not self.created_document_id or not self.created_item_id:
            print("⚠️  Skipping - No document or item ID available")
            return True
            
        update_data = {
            "quantity": 3.0,
            "unit_price": 75.00
        }
        
        success, response = self.run_test(
            "Update Item",
            "PUT",
            f"billing-documents/{self.created_document_id}/items/{self.created_item_id}",
            200,
            data=update_data
        )
        return success

    def test_remove_item(self):
        """Test removing an item from a document"""
        if not self.created_document_id or not self.created_item_id:
            print("⚠️  Skipping - No document or item ID available")
            return True
            
        success, response = self.run_test(
            "Remove Item",
            "DELETE",
            f"billing-documents/{self.created_document_id}/items/{self.created_item_id}",
            200
        )
        return success

    def test_delete_document(self):
        """Test deleting a document"""
        if not self.created_document_id:
            print("⚠️  Skipping - No document ID available")
            return True
            
        success, response = self.run_test(
            "Delete Document",
            "DELETE",
            f"billing-documents/{self.created_document_id}",
            200
        )
        return success

    def test_error_handling(self):
        """Test error handling for invalid requests"""
        print(f"\n🔍 Testing Error Handling...")
        
        # Test getting non-existent document
        success, _ = self.run_test(
            "Get Non-existent Document",
            "GET",
            "billing-documents/invalid-id",
            404
        )
        
        # Test creating document with invalid data
        invalid_data = {
            "billing_type": "Invalid Type",
            "billing_date": "invalid-date"
        }
        
        success2, _ = self.run_test(
            "Create Document with Invalid Data",
            "POST",
            "billing-documents",
            422  # Validation error
        )
        
        return success or success2  # At least one should work

def main():
    print("🚀 Starting Billing System API Tests")
    print("=" * 50)
    
    tester = BillingSystemAPITester()
    
    # Run all tests in sequence
    test_methods = [
        tester.test_root_endpoint,
        tester.test_dashboard_stats,
        tester.test_create_document,
        tester.test_get_documents,
        tester.test_get_single_document,
        tester.test_update_document,
        tester.test_add_item_to_document,
        tester.test_update_item,
        tester.test_remove_item,
        tester.test_delete_document,
        tester.test_error_handling
    ]
    
    for test_method in test_methods:
        try:
            test_method()
        except Exception as e:
            print(f"❌ Test failed with exception: {str(e)}")
    
    # Print final results
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {tester.tests_passed}/{tester.tests_run} tests passed")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All tests passed!")
        return 0
    else:
        print(f"⚠️  {tester.tests_run - tester.tests_passed} tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())