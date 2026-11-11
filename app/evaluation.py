"""Read-only evaluation helpers. Never fit a model or change its threshold."""
import math
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, confusion_matrix


def summarize(y, probabilities, threshold):
    y = np.asarray(y)
    probabilities = np.asarray(probabilities, dtype=float)
    if y.ndim != 1 or probabilities.shape != y.shape or not len(y):
        raise ValueError("Labels and probabilities must be nonempty matching vectors.")
    if not np.isin(y, [0, 1]).all() or not np.isfinite(probabilities).all():
        raise ValueError("Use binary labels and finite probabilities.")
    if not 0 <= threshold <= 1 or ((probabilities < 0) | (probabilities > 1)).any():
        raise ValueError("Threshold and probabilities must be between zero and one.")
    tn, fp, fn, tp = map(int, confusion_matrix(y, probabilities >= threshold, labels=[0, 1]).ravel())
    recall = tp / (tp + fn) if tp + fn else None
    precision = tp / (tp + fp) if tp + fp else None
    return dict(threshold=float(threshold), n=len(y), caught=tp, missed=fn, false_alarms=fp,
                correct_normal=tn, accuracy=(tp+tn)/len(y), recall=recall, precision=precision,
                baseline_accuracy=(tn+fp)/len(y), prevalence=(tp+fn)/len(y),
                average_precision=float(average_precision_score(y, probabilities)) if tp+fn else None,
                recall_interval=wilson(tp, tp+fn), precision_interval=wilson(tp, tp+fp))


def wilson(successes, total):
    """Approximate 95% binomial Wilson interval, conditional on this fixed split."""
    if total == 0:
        return None
    z = 1.959963984540054
    p = successes / total
    divisor = 1 + z*z/total
    center = (p + z*z/(2*total))/divisor
    margin = z*math.sqrt(p*(1-p)/total + z*z/(4*total*total))/divisor
    return [max(0., center-margin), min(1., center+margin)]


def outcomes(rows, threshold):
    result = rows.copy()
    failure = result["Actual failure"].eq(1)
    alarm = result["Failure probability"].ge(threshold)
    result["Outcome"] = np.select([failure & alarm, failure & ~alarm, ~failure & alarm],
                                  ["Caught failure", "Missed failure", "False alarm"], default="Correct normal")
    result["Preview threshold"] = threshold
    return result


def threshold_table(rows, saved_threshold):
    thresholds = sorted(set([round(i/100, 2) for i in range(5, 100, 5)] + [saved_threshold]))
    scores = [summarize(rows["Actual failure"], rows["Failure probability"], t) for t in thresholds]
    return pd.DataFrame([{ "Threshold": s["threshold"], "Caught failures": s["caught"],
                          "Missed failures": s["missed"], "False alarms": s["false_alarms"],
                          "Recall": s["recall"], "Precision": s["precision"]} for s in scores])
