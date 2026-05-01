import sys
import os

# Ensure the root directory is on the path so module imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agent.graph import mcp_agent

def main():
    print("🤖 Starting Agentic E2E Test Suite...")
    print("Note: This assumes the database is seeded with either seed.sql or large_seed.sql")

    test_cases = [
        {
            "name": "Test 1: Simple Aggregation (Users Count)",
            "query": "How many total users do we have in our system?",
            "expected_sql_keywords": ["SELECT", "COUNT", "users"],
            "expect_approval": False,
            # We check if the SQL correctly fetched a numeric total (15000 for large_seed.sql or 3 for seed.sql 'customers' if it used customer table due to query mapping)
            "expected_data_check": lambda data: len(data) == 1 and any(str(val).isdigit() for val in data[0].values()) if data else False
        },
        {
            "name": "Test 2: Modifying Query Security (HITL trigger)",
            "query": "Delete all orders where the status is Cancelled.",
            "expect_approval": True,
            "expected_data_check": lambda data: True # Handled before execution
        },
        {
            "name": "Test 3: Empty Data Edge Case (The Recent Bug Fix)",
            "query": "Show me products that cost exactly 0 dollars.",
            "expected_sql_keywords": ["SELECT", "WHERE"],
            "expect_approval": False,
            "expected_data_check": lambda data: len(data) == 0 if data is not None else False 
            # With our recent fix, returning 0 rows evaluates to an empty list [], not a success message.
        },
        {
            "name": "Test 4: Top N Query with Ordering",
            "query": "What are the top 3 most expensive products?",
            "expected_sql_keywords": ["SELECT", "ORDER BY", "DESC", "LIMIT"],
            "expect_approval": False,
            "expected_data_check": lambda data: len(data) == 3 if data else False
        }
    ]

    passed = 0
    failed = 0

    for idx, tc in enumerate(test_cases, 1):
        print(f"\n--- Running {tc['name']} ---")
        print(f"Query: \"{tc['query']}\"")
        
        initial_state = {
            "user_query": tc["query"],
            "correction_attempts": 0,
            "is_approved": False
        }
        
        try:
            # LangGraph limits us structurally, wait for resolution
            result_state = mcp_agent.invoke(initial_state)
            
            # Check Approval Workflow
            requires_app = result_state.get("requires_approval", False)
            if requires_app != tc["expect_approval"]:
                print(f"❌ FAILED: Expected requires_approval={tc['expect_approval']} but got {requires_app}")
                failed += 1
                continue
            
            if tc["expect_approval"]:
                print("✅ PASSED: Security approval correctly halted execution.")
                passed += 1
                continue

            # Check Execution Errors
            if result_state.get("execution_error"):
                print(f"❌ FAILED: Agent encountered DB error: {result_state['execution_error']}")
                failed += 1
                continue
                
            # Check SQL Keywords
            gen_sql = result_state.get("generated_sql", "").upper()
            missing_kw = [kw for kw in tc.get("expected_sql_keywords", []) if kw.upper() not in gen_sql]
            if missing_kw:
                print(f"❌ FAILED: Generated SQL missing expected keywords: {missing_kw}. SQL: {gen_sql}")
                failed += 1
                continue
                
            # Check Data payload
            data = result_state.get("final_results", [])
            if not tc["expected_data_check"](data):
                print(f"❌ FAILED: Data check failed. Received Data: {data}")
                failed += 1
                continue
                
            # Ensure final_answer exists and provides natural language fallback
            final_answer = result_state.get('final_answer', '')
            if not final_answer or len(final_answer) < 5:
                print(f"❌ FAILED: Agent did not return a valid natural language final answer.")
                failed += 1
                continue

            print(f"✅ PASSED! Final agent response snippet: {final_answer[:100]}...")
            passed += 1
            
        except Exception as e:
            print(f"❌ FAILED with Exception: {e}")
            failed += 1

    print("\n" + "="*40)
    print(f"🎯 TEST SUMMARY: {passed} Passed, {failed} Failed.")
    print("="*40)

if __name__ == "__main__":
    main()
