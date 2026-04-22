import pickle
import numpy as np


def load_ckpt(path):
    with open(path, 'rb') as f:
        weights = pickle.load(f)
    return weights


def check_ckpt_same(ckpt1_path, ckpt2_path):
    print(f"[对比] {ckpt1_path} vs {ckpt2_path}")

    w1 = load_ckpt(ckpt1_path)
    w2 = load_ckpt(ckpt2_path)

    # 1. 检查层数是否一样
    if len(w1) != len(w2):
        print(f"❌ 层数不同：w1={len(w1)}, w2={len(w2)}")
        return False

    all_same = True
    max_diff = 0.0

    # 2. 逐层检查
    for i, (a, b) in enumerate(zip(w1, w2)):
        if a.shape != b.shape:
            print(f"❌ 第{i}层 shape 不同：{a.shape} vs {b.shape}")
            return False

        diff = np.max(np.abs(a - b))
        max_diff = max(max_diff, diff)

        if diff > 1e-10:
            print(f"⚠️ 第{i}层 不同，最大差值：{diff:.8f}")
            all_same = False

    print("-" * 50)
    if all_same:
        print("✅ 两个 ckpt **完全相同**！")
    else:
        print(f"❌ 两个 ckpt **不一样**，全局最大差值：{max_diff:.8f}")
    print("-" * 50)
    return all_same


if __name__ == '__main__':
    # ===================== 在这里改你的两个文件路径 =====================
    CKPT1 = "45.ckpt"
    CKPT2 = "last.ckpt"
    # ====================================================================

    check_ckpt_same(CKPT1, CKPT2)