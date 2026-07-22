"""General nonlinear curve fitting for arbitrary user-supplied models.

A model is a formula in ``x`` plus any number of free parameters, e.g.
``a * exp(-b * x) + c``.  It may also reference other data columns by name —
those are treated as fixed covariates (extra independent variables), not as
fitted parameters, so ``a * x + b - offset`` fits ``a`` and ``b`` while using
the ``offset`` column's values.  Columns with spaces or names that clash with
a function are referenced with backticks (`` `flow rate` ``).  Parameter names
are discovered automatically as any identifier that is not ``x``, a known
column, a function, or a constant.  Fitting uses
:func:`scipy.optimize.curve_fit`.
"""
import ast
import warnings

import numpy as np
from scipy.optimize import OptimizeWarning, curve_fit

from .computedColumnDialog import FORMULA_NAMESPACE, columnRef, substituteColumns

# Names that are never treated as fit parameters.
_RESERVED = set(FORMULA_NAMESPACE) | {"x"}


def extractParameters(modelExpr, columns=()):
    """Return the sorted free-parameter names used in a model expression.

    Column names (in ``columns``, referenced bare or with backticks), ``x``,
    functions, and constants are excluded.  Raises SyntaxError if the
    expression cannot be parsed.
    """
    expr2, tokenMap = substituteColumns(modelExpr)
    tree = ast.parse(expr2, mode="eval")
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    colset = set(map(str, columns))
    excluded = _RESERVED | set(tokenMap) | {n for n in names if n in colset}
    return sorted(names - excluded)


def _bindings(extra, tokenMap):
    """Namespace entries for covariate columns: bound under their bare name
    (when a plain identifier) and under any backtick token that maps to them."""
    b = {}
    for name, arr in extra.items():
        if name.isidentifier() and name not in FORMULA_NAMESPACE:
            b[name] = arr
    for token, name in tokenMap.items():
        if name in extra:
            b[token] = extra[name]
    return b


def _makeModel(compiledExpr, paramNames, bindings):
    def model(x, *params):
        ns = dict(FORMULA_NAMESPACE)
        ns["x"] = x
        ns.update(bindings)                    # fixed covariate columns
        ns.update(zip(paramNames, params))
        return eval(compiledExpr, {"__builtins__": {}}, ns)  # noqa: S307

    return model


def fitCurve(x, y, modelExpr, p0=None, maxfev=10000, extra=None):
    """Fit ``modelExpr`` to (x, y), optionally using extra covariate columns.

    ``extra`` is a mapping of column-name → array (aligned with x and y); those
    names are available in the model as fixed data.

    Returns a dict with keys: paramNames, popt, perr, r2, equation, usesExtra,
    fittedX, fittedY, predict, warning.  Raises ValueError with a readable
    message on any failure.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    extra = {k: np.asarray(v, dtype=float) for k, v in (extra or {}).items()}

    mask = ~(np.isnan(x) | np.isnan(y))
    for v in extra.values():
        mask &= ~np.isnan(v)
    x, y = x[mask], y[mask]
    extra = {k: v[mask] for k, v in extra.items()}

    expr2, tokenMap = substituteColumns(modelExpr)
    paramNames = extractParameters(modelExpr, columns=extra.keys())
    if not paramNames:
        raise ValueError("Model has no free parameters to fit "
                         "(use names like a, b, c alongside x).")
    if len(x) < len(paramNames):
        raise ValueError(f"Need at least {len(paramNames)} points to fit "
                         f"{len(paramNames)} parameters; got {len(x)}.")

    code = compile(expr2, "<model>", "eval")
    bindings = _bindings(extra, tokenMap)
    model = _makeModel(code, paramNames, bindings)

    if p0 is None:
        p0 = [1.0] * len(paramNames)
    elif len(p0) != len(paramNames):
        raise ValueError(f"Expected {len(paramNames)} initial guesses "
                         f"({', '.join(paramNames)}); got {len(p0)}.")

    try:
        with np.errstate(over="ignore", invalid="ignore", divide="ignore"), \
                warnings.catch_warnings():
            warnings.simplefilter("ignore", OptimizeWarning)
            popt, pcov = curve_fit(model, x, y, p0=p0, maxfev=maxfev)
    except Exception as exc:                       # RuntimeError, TypeError, …
        raise ValueError(f"Fit did not converge: {exc}")

    with np.errstate(invalid="ignore"):
        perr = np.sqrt(np.diag(pcov))

    yAtData = np.asarray(model(x, *popt), dtype=float)
    resid = y - yAtData
    ssRes = float(np.sum(resid ** 2))
    ssTot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - ssRes / ssTot if ssTot > 0 else float("nan")

    warning = None
    if not np.all(np.isfinite(perr)):
        warning = ("Uncertainties could not be estimated — the fit may be "
                   "degenerate or over-parameterised.")

    # Build the display equation from the tokenized form so a parameter letter
    # can't be substituted inside a backtick column name, then restore columns.
    equation = expr2
    for name, val in zip(paramNames, popt):
        equation = _replaceIdentifier(equation, name, f"{val:.4g}")
    for token, colname in tokenMap.items():
        equation = equation.replace(token, columnRef(colname))

    order = np.argsort(x)

    def predict(xs):
        # Valid only for models with no covariate columns.
        return _makeModel(code, paramNames, {})(np.asarray(xs, dtype=float), *popt)

    return {
        "paramNames": paramNames,
        "popt": [float(v) for v in popt],
        "perr": [float(v) for v in perr],
        "r2": float(r2),
        "equation": equation,
        "usesExtra": bool(extra),
        "fittedX": x[order],
        "fittedY": yAtData[order],
        "predict": predict,
        "warning": warning,
    }


def _replaceIdentifier(expr, name, replacement):
    """Replace whole-word identifier `name` in `expr` with `replacement`."""
    import re
    return re.sub(rf"\b{re.escape(name)}\b", replacement, expr)
