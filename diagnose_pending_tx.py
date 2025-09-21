import os, time, json
from decimal import Decimal
from web3 import Web3
from eth_account import Account

# سرویس شما
from services.blockchains.ethereum_service import EthereumService

def gwei(w3, x): 
    return w3.to_wei(str(x), 'gwei')

def check_fee_sanity(w3, tx_params):
    blk = w3.eth.get_block('pending')
    base = blk.get('baseFeePerGas', w3.eth.gas_price)
    max_fee = tx_params.get('maxFeePerGas')
    tip = tx_params.get('maxPriorityFeePerGas', 0)
    problems = []
    if tip == 0:
        problems.append("priorityFee=0 → عملاً تراکنش جذاب نیست")
    if max_fee is not None and max_fee < base:
        problems.append(f"maxFeePerGas({w3.from_wei(max_fee,'gwei'):.2f} gwei) < baseFee({w3.from_wei(base,'gwei'):.2f} gwei)")
    return {
        "baseFee_gwei": float(w3.from_wei(base, 'gwei')),
        "maxFee_gwei": float(w3.from_wei(max_fee or 0, 'gwei')),
        "priority_gwei": float(w3.from_wei(tip or 0, 'gwei')),
        "problems": problems
    }

def visible_in_public_mempool(tx_hash, rpc_list):
    results = {}
    for url in rpc_list:
        try:
            w3 = Web3(Web3.HTTPProvider(url, request_kwargs={"timeout": 10}))
            ok = w3.is_connected()
            if not ok:
                results[url] = "conn-fail"
                continue
            tx = w3.eth.get_transaction(tx_hash)
            results[url] = "seen" if tx else "not-seen"
        except Exception as e:
            # اکثر RPCها اگر ندیده باشند، Exception می‌دهند
            results[url] = f"not-seen ({str(e)[:60]})"
    return results

def speed_profile(w3, speed: str):
    blk = w3.eth.get_block('pending')
    base = blk.get('baseFeePerGas', w3.eth.gas_price)
    if speed == "slow":
        tip = gwei(w3, 1.5); safety = gwei(w3, 12)
    elif speed == "fast":
        tip = gwei(w3, 4); safety = gwei(w3, 35)
    else:  # medium
        tip = gwei(w3, 2); safety = gwei(w3, 22)
    return tip, base + tip + safety

def build_tx(w3, sender, to, amount_eth, speed="medium"):
    nonce = w3.eth.get_transaction_count(w3.to_checksum_address(sender), 'pending')
    tip, max_fee = speed_profile(w3, speed)
    return {
        'type': 2,
        'from': w3.to_checksum_address(sender),
        'to': w3.to_checksum_address(to),
        'value': w3.to_wei(Decimal(str(amount_eth)), 'ether'),
        'gas': 21000,
        'maxPriorityFeePerGas': tip,
        'maxFeePerGas': max_fee,
        'nonce': nonce,
        'chainId': w3.eth.chain_id
    }

def diagnose_send(sender, privkey, to, amount_eth=Decimal("0.0001"), speed="medium"):
    svc = EthereumService()  # از RPCهای primary/backup خودش استفاده می‌کند
    w3 = svc.w3

    # 1) ساخت تراکنش type-2 و بررسی sanity
    tx = build_tx(w3, sender, to, amount_eth, speed)
    fee_check = check_fee_sanity(w3, tx)
    print("[fee-check]", json.dumps(fee_check, ensure_ascii=False, indent=2))

    # 2) امضا و برادکست به چند RPC (از متد داخلی سرویس استفاده می‌کنیم)
    signed = w3.eth.account.sign_transaction(tx, privkey)
    tx_hash = svc._broadcast_transaction_multi_rpc(signed)  # چند RPC برای انتشار عمومی. :contentReference[oaicite:1]{index=1}
    print(f"[broadcast] tx_hash = {tx_hash}")

    # 3) بررسی دیده‌شدن در مم‌پول عمومی بین چند RPC
    rpcs = [svc.primary_rpc] + svc.backup_rpcs[:3]
    vis = visible_in_public_mempool(tx_hash, rpcs)
    print("[mempool-visibility]", json.dumps(vis, ensure_ascii=False, indent=2))

    # 4) پایش وضعیت برای چند دقیقه (pending → mined یا dropped)
    for i in range(12):  # ~۶۰ ثانیه با sleep 5s
        try:
            rcpt = w3.eth.get_transaction_receipt(tx_hash)
            if rcpt and rcpt.get('blockNumber'):
                print(f"[status] MINED in block {rcpt['blockNumber']}")
                break
        except Exception:
            pass
        print(f"[status] still pending... t={i*5}s")
        time.sleep(5)
    else:
        print("[status] still pending after 60s")

    # 5) اگر هنوز pending ماند، پیشنهاد speed-up/cancel
    #    (خود ارسال جایگزین را انجام نمی‌دهیم؛ فقط پارامترهای مناسب را چاپ می‌کنیم)
    if fee_check["problems"] or "still pending" in locals():
        same_nonce = tx["nonce"]
        tip_fast, max_fast = speed_profile(w3, "fast")
        suggest_replace = {
            "nonce": same_nonce,
            "priority_gwei": float(w3.from_wei(tip_fast,'gwei')),
            "maxFee_gwei": float(w3.from_wei(max_fast,'gwei')),
            "action": "speed-up (same to/value, same nonce)"
        }
        suggest_cancel = {
            "nonce": same_nonce,
            "priority_gwei": float(w3.from_wei(tip_fast,'gwei')),
            "maxFee_gwei": float(w3.from_wei(max_fast,'gwei')),
            "to": sender, "value_eth": "0",
            "action": "cancel (send 0 ETH to self with same nonce)"
        }
        print("[suggested-replacement]", json.dumps(suggest_replace, ensure_ascii=False, indent=2))
        print("[suggested-cancel]", json.dumps(suggest_cancel, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    # مقادیر نمونه؛ جایگزین کن
    SENDER = "0xYourSender"
    PRIVKEY = "0xYourPrivKey"
    RECIPIENT = "0x8d697D386c175dC7ac25DF67f82B3BFbc8EC5bE9"
    diagnose_send(SENDER, PRIVKEY, RECIPIENT, Decimal("0.0001"), speed="medium")
