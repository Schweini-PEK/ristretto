"""
Deterministic subroutines that support randomized algorithms.
These subroutines don't go into rblas, because we won't be asking
vendors to optimize their performance.
"""
from scipy.linalg import solve_triangular
import scipy.sparse.linalg as sparla
import numpy as np


def a_times_inv_r(A, R):
    """Return a linear operator that represents A @ inv(R) """

    work = np.zeros(A.shape[1])

    def mv(vec):
        np.copyto(work, vec)
        solve_triangular(R, work, lower=False, check_finite=False,
                         overwrite_b=True)
        return A @ work

    def rmv(vec):
        np.dot(A.T, vec, out=work)
        return solve_triangular(R, work, 'T', lower=False, check_finite=False)

    A_precond = sparla.LinearOperator(shape=A.shape, matvec=mv, rmatvec=rmv)
    return A_precond


def upper_tri_precond_lsqr(A, b, R, tol, iter_lim, x0=None):
    """
    Run preconditioned LSQR to obtain an approximate solution to
        min{ || A @ x - b ||_2 : x in R^m }
    where A.shape = (n, m) has n >> m, so the problem is over-determined.

    Parameters
    ----------
    A : ndarray
        Data matrix with n rows and m columns. Columns are presumed linearly
        independent (for now).
    b : ndarray
        Right-hand-side b.shape = (n,).
    R : ndarray
        The upper-triangular preconditioner, has R.shape = (m, m).
    tol : float
        Must be positive. Stopping criteria for LSQR.
    iter_lim : int
        Must be positive. Stopping criteria for LSQR.
    x0 : Union[None, ndarray]
        If provided, use as an initial approximate solution to (A'A) x = A' b.
        Internally, we initialize preconditioned lsqr at y0 = R x0.
    Returns
    -------
    The same values as SciPy's lsqr implementation.
    """
    A_precond = a_times_inv_r(A, R)
    if x0 is not None:
        y0 = (R @ x0).ravel()
        result = sparla.lsqr(A_precond, b, atol=tol, btol=tol,
                             iter_lim=iter_lim, x0=y0)
    else:
        result = sparla.lsqr(A_precond, b, atol=tol, btol=tol,
                             iter_lim=iter_lim)
    solve_triangular(R, result[0], lower=False, overwrite_b=True)
    return result


def pinv_precond_lsqr(A, b, N, tol, iter_lim):
    """
    Run preconditioned LSQR to obtain an approximate solution to
        min{ || A @ x - b ||_2 : x in R^m }
    where A.shape = (n, m) has n >> m, so the problem is over-determined.

    Parameters
    ----------
    A : ndarray
        Data matrix with n rows and m columns.
    b : ndarray
        Right-hand-side b.shape = (n,).
    N : ndarray
        The condition number of A @ N should be near one and its rank should be
        the same as that of A.
    tol : float
        Must be positive. Stopping criteria for LSQR.
    iter_lim : int
        Must be positive. Stopping criteria for LSQR.

    Returns
    -------
    The same values as SciPy's lsqr implementation.
    """
    work = np.zeros(A.shape[1])

    def mv(vec):
        np.dot(N, vec, out=work)
        return A @ work

    def rmv(vec):
        np.dot(A.T, vec, out=work)
        return N.T @ work

    A_precond = sparla.LinearOperator(shape=(A.shape[0], N.shape[1]),
                                      matvec=mv, rmatvec=rmv)
    result = sparla.lsqr(A_precond, b, atol=tol, btol=tol, iter_lim=iter_lim)
    result = (N @ result[0],) + result[1:]
    return result


def lr_precond_gram(A, R):
    """Return a linear operator that represents (A @ inv(R)).T @ (A @ inv(R))"""

    work1 = np.zeros(A.shape[1])
    work2 = np.zeros(A.shape[0])

    def mv(vec):
        np.copyto(work1, vec)
        solve_triangular(R, work1, lower=False, check_finite=False,
                         overwrite_b=True)
        np.dot(A, work1, out=work2)
        np.dot(A.T, work2, out=work1)
        res = solve_triangular(R, work1, 'T', lower=False, check_finite=False)
        return res

    AtA_precond = sparla.LinearOperator(shape=(A.shape[1], A.shape[1]),
                                        matvec=mv, rmatvec=mv)
    return AtA_precond


def upper_tri_precond_cg(A, b, R, tol, iter_lim, x0=None):
    """
    Run conjugate gradients on the positive semidefinite linear system
        ((A R^-1)' (A R^-1)) y == (R^-1)' b
    and set x = R^-1 y, as a means to solve the linear system
        (A' A) x = b.

    Parameters
    ----------
    A : np.ndarray
        Tall data matrix.
    b : np.ndarray
        right-hand-side. Same number of columns as A.
    R : np.ndarray
        Nonsingular upper-triangular preconditioner.
        The condition number of (A R^-1) should be near one.
    tol : float
        Stopping criteria for ScPy's cg implementation.
        Considered with respect to the preconditioned system.
    iter_lim : int
        Stopping criteria for SciPy's cg implementation
    x0 : Union[None, np.ndarray]
        If provided, use as an initial solution to (A' A) x = b.

    Returns
    -------
    The same values as SciPy's cg implementation.
    """
    AtA_precond = lr_precond_gram(A, R)
    b_precond = solve_triangular(R, b, 'T', lower=False, check_finite=False)
    if x0 is not None:
        y0 = (R @ x0).ravel()
        result = sparla.cg(AtA_precond, b_precond, atol=tol, btol=tol,
                           iter_lim=iter_lim, x0=y0)
    else:
        result = sparla.cg(AtA_precond, b_precond, atol=tol, btol=tol,
                           iter_lim=iter_lim)
    solve_triangular(R, result[0], lower=False, overwrite_b=True)
    return result
