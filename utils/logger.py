from colorama import Fore, Style, init
init(autoreset=True)

def section(domain: str, index: int, total: int):
    print(f"\n{Fore.CYAN}{'='*55}")
    print(f"  [scan] [{index}/{total}] {domain}")
    print(f"{'='*55}{Style.RESET_ALL}")

def node_start(num: int, name: str):
    print(f"  {Fore.WHITE}> Node {num}: {name}...{Style.RESET_ALL}")

def found(node: int, email: str):
    print(f"  {Fore.GREEN}[found] Email found in Node {node} -> jumping to Node 8 (final verify)")
    print(f"     {email}{Style.RESET_ALL}")

def skip(reason: str):
    print(f"  {Fore.YELLOW}[skip] {reason}{Style.RESET_ALL}")

def verified(email: str, result: dict):
    icon = "OK" if result.get("overall") == "valid" else "NO"
    print(f"""
  {icon} Verification Result:
  {'-'*34}
  Email:         {email}
  Overall:       {result.get('overall','?').upper()}
  Format:        {result.get('format','?')}
  Professional:  {result.get('professional','?')}
  Domain Status: {result.get('domain','?')}
  Mailbox:       {result.get('mailbox','?')}
  {'-'*34}""")

def node_report(node_trace: list[dict]):
    print("\n  Node Summary:")
    print(f"  {'-'*34}")
    for item in node_trace:
        detail = item.get("detail", "")
        print(
            f"  Node {item['node']:>2} | {item['status']:<9} | "
            f"{item['role']} | {detail}"
        )
    print(f"  {'-'*34}")

def not_found(domain: str):
    print(f"  {Fore.RED}[none] No email found for {domain}{Style.RESET_ALL}")

def done(total: int, found_count: int):
    print(f"\n{Fore.GREEN}{'='*55}")
    print(f"  Done. {found_count}/{total} emails found.")
    print("  Results saved to output/results.csv")
    print(f"{'='*55}{Style.RESET_ALL}\n")
