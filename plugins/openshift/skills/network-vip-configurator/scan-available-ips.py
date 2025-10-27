#!/usr/bin/env python3
"""
scan-available-ips.py - Scan subnet for available IP addresses for VIPs

This script scans a subnet CIDR to find available IP addresses by:
1. Pinging IPs to check if they respond
2. Optionally checking Route53 for existing A records
3. Returning a list of available IPs suitable for API and Ingress VIPs
"""

import argparse
import ipaddress
import json
import subprocess
import sys
import concurrent.futures


def parse_cidr(cidr):
    """Parse CIDR notation to get network object"""
    try:
        return ipaddress.ip_network(cidr, strict=False)
    except ValueError as e:
        raise ValueError(f"Invalid CIDR notation '{cidr}': {e}")


def ping_ip(ip, timeout=1, count=2):
    """
    Ping an IP address to check if it's in use

    Returns:
        bool: True if IP responds to ping, False otherwise
    """
    try:
        # Use -W for timeout on Linux, -t on macOS
        cmd = ['ping', '-c', str(count), '-W', str(timeout), str(ip)]
        result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout * count + 1
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return False
    except Exception:
        return False


def check_route53_record(ip, hosted_zone_id=None):
    """
    Check if IP exists in Route53 A records

    Args:
        ip: IP address to check
        hosted_zone_id: Route53 hosted zone ID (optional)

    Returns:
        tuple: (exists: bool, record_name: str or None)
    """
    if not hosted_zone_id:
        # Skip Route53 check if no zone ID provided
        return False, None

    try:
        # Query Route53 for A records matching this IP
        cmd = [
            'aws', 'route53', 'list-resource-record-sets',
            '--hosted-zone-id', hosted_zone_id,
            '--query', f"ResourceRecordSets[?Type=='A' && ResourceRecords[0].Value=='{ip}'].Name",
            '--output', 'text'
        ]

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=10
        )

        if result.returncode == 0 and result.stdout.strip():
            return True, result.stdout.strip()

        return False, None

    except subprocess.TimeoutExpired:
        print(f"Warning: Route53 query timeout for {ip}", file=sys.stderr)
        return False, None
    except Exception as e:
        print(f"Warning: Route53 query failed for {ip}: {e}", file=sys.stderr)
        return False, None


def scan_ip(ip, hosted_zone_id=None, verbose=False):
    """
    Scan a single IP to determine if it's available

    Returns:
        dict: {
            'ip': str,
            'available': bool,
            'ping_response': bool,
            'in_route53': bool,
            'route53_record': str or None
        }
    """
    ip_str = str(ip)

    if verbose:
        print(f"Scanning {ip_str}...", file=sys.stderr)

    # Check ping
    ping_response = ping_ip(ip_str)

    # Check Route53
    in_route53, route53_record = check_route53_record(ip_str, hosted_zone_id)

    # IP is available if it doesn't respond to ping AND is not in Route53
    available = not ping_response and not in_route53

    return {
        'ip': ip_str,
        'available': available,
        'ping_response': ping_response,
        'in_route53': in_route53,
        'route53_record': route53_record
    }


def scan_subnet(cidr, hosted_zone_id=None, max_candidates=10, skip_first=10, skip_last=10, max_workers=20, verbose=False):
    """
    Scan subnet CIDR for available IP addresses

    Args:
        cidr: Subnet CIDR (e.g., "10.0.0.0/24")
        hosted_zone_id: Route53 hosted zone ID (optional)
        max_candidates: Maximum number of available IPs to return
        skip_first: Skip first N IPs in subnet (network, gateway, etc.)
        skip_last: Skip last N IPs in subnet (broadcast, etc.)
        max_workers: Maximum parallel workers for scanning
        verbose: Print progress to stderr

    Returns:
        list: List of available IP dictionaries
    """
    network = parse_cidr(cidr)

    # Get list of IPs to scan
    all_ips = list(network.hosts())

    if len(all_ips) <= skip_first + skip_last:
        raise ValueError(f"Subnet too small: only {len(all_ips)} usable IPs")

    # Skip first and last N IPs
    ips_to_scan = all_ips[skip_first:-skip_last] if skip_last > 0 else all_ips[skip_first:]

    if verbose:
        print(f"Scanning {len(ips_to_scan)} IPs in subnet {cidr}...", file=sys.stderr)
        print(f"Skipped first {skip_first} and last {skip_last} IPs", file=sys.stderr)

    # Scan IPs in parallel
    available_ips = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(scan_ip, ip, hosted_zone_id, verbose): ip
            for ip in ips_to_scan
        }

        for future in concurrent.futures.as_completed(futures):
            result = future.result()

            if result['available']:
                available_ips.append(result)

                if verbose:
                    print(f"✓ Found available IP: {result['ip']}", file=sys.stderr)

                # Stop when we have enough candidates
                if len(available_ips) >= max_candidates:
                    # Cancel remaining futures
                    for f in futures:
                        f.cancel()
                    break

    # Sort by IP address
    available_ips.sort(key=lambda x: ipaddress.ip_address(x['ip']))

    return available_ips[:max_candidates]


def main():
    parser = argparse.ArgumentParser(
        description='Scan subnet for available IP addresses for OpenShift VIPs',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scan subnet for available IPs
  %(prog)s 10.0.0.0/24

  # Scan with Route53 integration
  %(prog)s 10.0.0.0/24 --zone-id Z1234567890ABC

  # Get more candidates
  %(prog)s 10.0.0.0/24 --max-candidates 20

  # Verbose output
  %(prog)s 10.0.0.0/24 --verbose

Output format (JSON):
  [
    {
      "ip": "10.0.0.100",
      "available": true,
      "ping_response": false,
      "in_route53": false,
      "route53_record": null
    },
    ...
  ]
        """
    )

    parser.add_argument(
        'cidr',
        help='Subnet CIDR to scan (e.g., 10.0.0.0/24)'
    )

    parser.add_argument(
        '--zone-id',
        help='Route53 hosted zone ID for DNS checking (optional)'
    )

    parser.add_argument(
        '--max-candidates',
        type=int,
        default=10,
        help='Maximum number of available IPs to return (default: 10)'
    )

    parser.add_argument(
        '--skip-first',
        type=int,
        default=10,
        help='Skip first N IPs in subnet (default: 10)'
    )

    parser.add_argument(
        '--skip-last',
        type=int,
        default=10,
        help='Skip last N IPs in subnet (default: 10)'
    )

    parser.add_argument(
        '--max-workers',
        type=int,
        default=20,
        help='Maximum parallel workers (default: 20)'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Print progress to stderr'
    )

    parser.add_argument(
        '--pretty',
        action='store_true',
        help='Pretty-print JSON output'
    )

    args = parser.parse_args()

    try:
        # Scan subnet
        available_ips = scan_subnet(
            args.cidr,
            hosted_zone_id=args.zone_id,
            max_candidates=args.max_candidates,
            skip_first=args.skip_first,
            skip_last=args.skip_last,
            max_workers=args.max_workers,
            verbose=args.verbose
        )

        if args.verbose:
            print(f"\n✓ Found {len(available_ips)} available IP(s)", file=sys.stderr)

        # Output JSON
        if args.pretty:
            print(json.dumps(available_ips, indent=2))
        else:
            print(json.dumps(available_ips))

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
