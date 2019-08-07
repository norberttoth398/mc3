# Copyright (c) 2015-2019 Patricio Cubillos and contributors.
# MC3 is open-source software under the MIT license (see LICENSE).

__all__ = ['sample']

import os
import sys
import importlib
import multiprocessing as mpr
from datetime import date

if sys.version_info.major == 2:
    range = xrange

import numpy as np
import matplotlib as mpl
if os.environ.get('DISPLAY', '') == '':
    mpl.use('Agg')
import matplotlib.pyplot as plt

from .fit_driver import fit
from .mcmc_driver import mcmc
from . import utils   as mu
from . import stats   as ms
from . import plots   as mp
from .VERSION import __version__


@mu.ignore_system_exit
def sample(data=None, uncert=None, func=None, params=None, indparams=[],
           pmin=None, pmax=None, pstep=None,
           prior=None, priorlow=None, priorup=None,
           sampler=None, ncpu=None, leastsq=None, chisqscale=False,
           nchains=7, nsamples=None, burnin=0, thinning=1,
           grtest=True, grbreak=0.0, grnmin=0.5, wlike=False,
           fgamma=1.0, fepsilon=0.0, hsize=10, kickoff='normal',
           plots=False, ioff=False, showbp=True, savefile=None, resume=False,
           rms=False, log=None, pnames=None, texnames=None,
           parname=None, nproc=None, stepsize=None,
           full_output=None, chireturn=None, lm=None, walk=None):
  """
  This beautiful piece of code executes an MCMC or NS posterior sampling.

  Parameters
  ----------
  data: 1D float ndarray or string
      Data to be fit by func.  If string, path to file containing data.
  uncert: 1D float ndarray
      Uncertainties of data.
  func: Callable or string-iterable
      The callable function that models data as:
          model = func(params, *indparams)
      Or an iterable of 3 strings (funcname, modulename, path)
      that specifies the function name, function module, and module path.
      If the module is already in the python-path scope, path can be omitted.
  params: 1D float ndarray or string
      Set of initial fitting parameters for func.
      If string, path to file containing data.
  indparams: tuple or string
      Additional arguments required by func.  If string, path to file
      containing indparams.
  pmin: 1D ndarray
      Lower boundaries for the posterior exploration.
  pmax: 1D ndarray
      Upper boundaries for the posterior exploration.
  pstep: 1D ndarray
      Parameter stepping behavior.
      - Free parameters have pstep>0.
      - Fixed parameters have pstep=0.
      - Negative values indicate a shared parameter, with pstep set to
        the negative index of the sharing parameter (starting the count
        from 1), e.g.: to share second parameter and first one, do:
        pstep[1] = -1.
      For MCMC, the pstep value of free parameters set the scale of the
      initial jump proposal.
  prior: 1D ndarray
      Parameter priors.  The type of prior is determined by priorlow
      and priorup:
          if both priorlow>0 and priorup>0   Gaussian
          else                               Uniform between [pmin,pmax]
  priorlow: 1D ndarray
      Lower prior uncertainty values.
  priorup: 1D ndarray
      Upper prior uncertainty values.
  sampler: String
      Sampling algorithm:
      - 'mrw':  Metropolis random walk.
      - 'demc': Differential Evolution Markov chain.
      - 'snooker': DEMC-z with snooker update.
  ncpu: Integer
      Number of processors for the MCMC chains (MC3 defaults to
      one CPU for each chain plus a CPU for the central hub).
  leastsq: String
      If not None, perform a least-square optimization before the MCMC run.
      Select from:
          'lm':  Levenberg-Marquardt (most efficient, but does not obey bounds)
          'trf': Trust Region Reflective
  chisqscale: Boolean
      Scale the data uncertainties such that the reduced chi-square = 1.
  nchains: Scalar
      Number of simultaneous chains to run.
  nsamples: Scalar
      Total number of samples.
  burnin: Integer
      Number of burned-in (discarded) number of iterations at the beginning
      of the chains.
  thinning: Integer
      Thinning factor of the chains (use every thinning-th iteration) used
      in the GR test and plots.
  wlike: Bool
      If True, calculate the likelihood in a wavelet-base.  This requires
      three additional parameters (TBD: this needs documentation).
  grtest: Boolean
      If True, run Gelman & Rubin test.
  grbreak: Float
      Gelman-Rubin convergence threshold to stop the MCMC (I'd suggest
      grbreak ~ 1.001--1.005).  Do not break if grbreak=0.0 (default).
  grnmin: Integer or float
      Minimum number of samples required for grbreak to stop the MCMC.
      If grnmin > 1: grnmin sets the minimum required number of samples.
      If 0 < grnmin < 1: grnmin sets the minimum required nsamples fraction.
  fgamma: Float
      Proposals jump scale factor for DEMC's gamma.
      The code computes: gamma = fgamma * 2.38 / sqrt(2*Nfree)
  fepsilon: Float
      Jump scale factor for DEMC's support distribution.
      The code computes: e = fepsilon * Normal(0, pstep)
  hsize: Integer
      Number of initial samples per chain.
  kickoff: String
      Flag to indicate how to start the chains:
      'normal' for normal distribution around initial guess, or
      'uniform' for uniform distribution withing the given boundaries.
  plots: Bool
      If True plot parameter traces, pairwise-posteriors, and posterior
      histograms.
  ioff: Bool
      If True, set plt.ioff(), i.e., do not display figures on screen.
  showbp: Bool
      If True, show best-fitting values in histogram and pairwise plots.
  savefile: String
      If not None, filename to store allparams and other MCMC results.
  resume: Boolean
      If True resume a previous run.
  rms: Boolean
      If True, calculate the RMS of the residuals: data - best_model.
  log: String or mc3.utils.Log instance
      Filename (as string) or log handler (as Log instance) handle logging.
  pnames: 1D string iterable
      List of parameter names (including fixed and shared parameters)
      to display on output screen and figures.  See also texnames.
      Screen output trims up to the 11th character.
      If not defined, default to texnames.
  texnames: 1D string iterable
      Parameter names for figures, which may use latex syntax.
      If not defined, default to pnames.

  Deprecated Parameters
  ---------------------
  parname: 1D string ndarray
      Deprecated, use pnames instead.
  nproc: Integer
      Deprecated, use ncpu instead.
  stepsize: 1D ndarray
      Deprecated, use pstep instead.
  chireturn:
      Deprecated.
  full_output:  Bool
      Deprecated.
  lm: Bool
      Deprecated, see leastsq.
  walk: String
      Deprecated, use sampler instead.

  Returns
  -------
  mc3_output: Dict
      A Dictionary containing the MCMC posterior distribution and related
      stats, including:
      - posterior: thinned posterior distribution of shape [nsamples, nfree],
            including the burn-in phase.
      - zchain: chain indices for the posterior samples.
      - zmask: posterior mask to remove the burn-in.
      - chisq: chi^2 values for the posterior samples.
      - log_post: -2*log(posterior) for the posterior samples (see Notes).
      - burnin: number of burned-in samples per chain.
      - meanp: mean of the marginal posteriors.
      - stdp: standard deviation of the marginal posteriors.
      - CRlo: lower boundary of the marginal 68%-highest posterior
            density (the credible region).
      - CRhi: upper boundary of the marginal 68%-HPD.
      - bestp: model parameters for the optimal log(posterior) in the sample.
      - best_log_post: optimal log(posterior) in the sample (see Notes).
      - best_model: model evaluated at bestp.
      - best_chisq: chi^2 for the optimal log(posterior) in the sample.
      - red_chisq: reduced chi-square: chi^2/(ndata-nfree) for the
            best-fitting sample.
      - BIC: Bayesian Information Criterion: chi^2 - nfree*log(ndata)
            for the best-fitting sample.
      - chisq_factor: Uncertainties scale factor to enforce chi^2_red = 1.
      - stddev_residuals: standard deviation of the residuals.
      - acceptance_rate: sample's acceptance rate.

  Notes
  -----
  The log_post variable is defined here as:
      log_post = -2*log(posterior)
               = -2*log(likelihood) - 2*log(prior)
               = chi-squared + log_prior
               = sum_i ((data[i] - model[i])/uncert[i])**2 + log_prior

  with log_prior defined as the negative-log of the prior
  (plus a constant, neglected since it does not affect the optimization):
  For a uniform prior:   log_prior = 0.0
  For a Gaussian prior:  log_prior = ((params - prior)/prior_uncert)**2

  Examples
  --------
  >>> import numpy as np
  >>> import mc3

  >>> def quad(p, x):
  >>>     return p[0] + p[1]*x + p[2]*x**2.0

  >>> # Preamble, create a noisy synthetic dataset:
  >>> np.random.seed(3)
  >>> x = np.linspace(0, 10, 100)
  >>> p_true = [3, -2.4, 0.5]
  >>> y = quad(p_true, x)
  >>> uncert = np.sqrt(np.abs(y))
  >>> data = y + np.random.normal(0, uncert)

  >>> # Initial guess for fitting parameters:
  >>> params = np.array([ 3.0, -2.0,  0.1])
  >>> pstep  = np.array([ 1.0,  1.0,  1.0])
  >>> pmin   = np.array([ 0.0, -5.0, -1.0])
  >>> pmax   = np.array([10.0,  5.0,  1.0])

  >>> # Gaussian prior on first parameter, uniform on second and third:
  >>> prior    = np.array([3.5, 0.0, 0.0])
  >>> priorlow = np.array([0.1, 0.0, 0.0])
  >>> priorup  = np.array([0.1, 0.0, 0.0])

  >>> indparams = [x]
  >>> func = quad
  >>> ncpu = 7

  >>> # MCMC sampling:
  >>> mcmc_output = mc3.sample(data, uncert, func, params, indparams=indparams,
  >>>     sampler='snooker', pstep=pstep, ncpu=ncpu, pmin=pmin, pmax=pmax,
  >>>     prior=prior, priorlow=priorlow, priorup=priorup,
  >>>     leastsq='lm', nsamples=1e5, burnin=1000, plots=True)

  >>> # See more examples and details at:
  >>> # https://mc3.readthedocs.io/en/latest/mcmc_tutorial.html
  """
  # Logging object:
  if isinstance(log, str):
      log = mu.Log(log, append=resume)
      closelog = True
  else:
      closelog = False
      if log is None:
          log = mu.Log()

  log.msg("\n{:s}\n"
      "  Multi-core Markov-chain Monte Carlo (MC3).\n"
      "  Version {}.\n"
      "  Copyright (c) 2015-{:d} Patricio Cubillos and collaborators.\n"
      "  MC3 is open-source software under the MIT license (see LICENSE).\n"
      "{:s}\n\n".format(log.sep, __version__, date.today().year, log.sep))

  # Deprecation warnings (to be removed not before summer 2020):
  if parname is not None:
      log.warning("parname argument is deprecated. Use pnames instead.")
      if pnames is None:
          pnames = parname
  if nproc is not None:
      log.warning("nproc argument is deprecated. Use ncpu instead.")
      if ncpu is None:
          ncpu = nproc
  if stepsize is not None:
      log.warning("stepsize argument is deprecated. Use pstep instead.")
      if pstep is None:
          pstep = stepsize
  if walk is not None:
      log.warning("walk argument is deprecated. Use sampler instead.")
      if sampler is None:
          sampler = walk
  if chireturn is not None:
      log.warning("chireturn argument is deprecated.")
  if full_output is not None:
      log.warning("full_output argument is deprecated.")

  if isinstance(leastsq, bool):
      if leastsq is True:
          leastsq = 'trf' if lm is False else 'lm'
      elif leastsq is False:
          leastsq = None
      log.warning("leastsq as boolean is deprecated.  See docs for new "
          "usage.  Set leastsq={}".format(repr(leastsq)))
  if isinstance(lm, bool):
      log.warning('lm argument is deprecated.  See new usage of leastsq.  '
          'Set leastsq={}'.format(repr(leastsq)))

  if sampler is None:
      log.error("'sampler' is a required argument.")
  if nsamples is None and sampler in ['MRW', 'DEMC', 'snooker']:
      log.error("'nsamples' is a required argument for MCMC runs.")
  if leastsq not in [None, 'lm', 'trf']:
      log.error("Invalid 'leastsq' input ({}). Must select from "
                "['lm', 'trf'].".format(leastsq))

  # Read the model parameters:
  params = mu.isfile(params, 'params', log, 'ascii', False, not_none=True)
  # Unpack if necessary:
  if np.ndim(params) > 1:
      ninfo, ndata = np.shape(params)
      if ninfo == 7:         # The priors
          prior    = params[4]
          priorlow = params[5]
          priorup  = params[6]
      if ninfo >= 4:         # The stepsize
          pstep    = params[3]
      if ninfo >= 3:         # The boundaries
          pmin     = params[1]
          pmax     = params[2]
      else:
          log.error('Invalid format/shape for params input file.')
      params = params[0]     # The initial guess
  params = np.array(params)

  # Process data and uncertainties:
  data = mu.isfile(data, 'data', log, 'bin', False, not_none=True)
  if np.ndim(data) > 1:
      data, uncert = data
  # Make local 'uncert' a copy, to avoid overwriting:
  if uncert is None:
      log.error("'uncert' is a required argument.")
  uncert = np.copy(uncert)

  # Process the independent parameters:
  if indparams != []:
      indparams = mu.isfile(indparams, 'indparams', log, 'bin', unpack=False)

  if ioff:
      plt.ioff()

  if resume:
      log.msg("\n\n{:s}\n{:s}  Resuming previous MCMC run.\n\n".
              format(log.sep, log.sep))

  # Import the model function:
  if isinstance(func, (list, tuple, np.ndarray)):
      if len(func) == 3:
          sys.path.append(func[2])
      else:
          sys.path.append(os.getcwd())
      fmodule = importlib.import_module(func[1])
      func = getattr(fmodule, func[0])
  elif not callable(func):
      log.error("'func' must be either a callable or an iterable of strings "
                "with the model function, file, and path names.")

  if ncpu is None and sampler in ['snooker', 'demc', 'mrw']:
      ncpu = nchains
  # Cap the number of processors:
  if ncpu >= mpr.cpu_count():
      log.warning("The number of requested CPUs ({:d}) is >= than the number "
                  "of available CPUs ({:d}).  Enforced ncpu to {:d}.".
                 format(ncpu, mpr.cpu_count(), mpr.cpu_count()-1))
      ncpu = mpr.cpu_count() - 1

  nparams = len(params)
  ndata   = len(data)

  # Setup array of parameter names:
  if   pnames is None     and texnames is not None:
      pnames = texnames
  elif pnames is not None and texnames is None:
      texnames = pnames
  elif pnames is None     and texnames is None:
      pnames = texnames = mu.default_parnames(nparams)
  pnames   = np.asarray(pnames)
  texnames = np.asarray(texnames)

  if pmin is None:
      pmin = np.tile(-np.inf, nparams)
  if pmax is None:
      pmax = np.tile( np.inf, nparams)
  pmin = np.asarray(pmin)
  pmax = np.asarray(pmax)
  if (np.any(np.isinf(pmin)) or np.any(np.isinf(pmax))) and sampler=='dynesty':
      log.error('Parameter space must be constrained by pmin and pmax.')

  if pstep is None:
      pstep = 0.1 * np.abs(params)
  pstep = np.asarray(pstep)

  # Set prior parameter indices:
  if prior is None or priorup is None or priorlow is None:
      prior = priorup = priorlow = np.zeros(nparams)

  # Check that initial values lie within the boundaries:
  if np.any(params < pmin) or np.any(params > pmax):
      pout = ""
      for pname, par, minp, maxp in zip(pnames, params, pmin, pmax):
          if par < minp:
              pout += "\n{:11s}  {: 12.5e} < {: 12.5e}".format(
                  pname[:11], minp, par)
          if par > maxp:
              pout += "\n{:26s}  {: 12.5e} > {: 12.5e}".format(
                  pname[:11], par, maxp)

      log.error("Some initial-guess values are out of bounds:\n"
                "Param name           pmin          value           pmax\n"
                "-----------  ------------   ------------   ------------"
                "{:s}".format(pout))

  nfree  = int(np.sum(pstep > 0))   # Number of free parameters
  ifree  = np.where(pstep > 0)[0]   # Free parameter indices
  ishare = np.where(pstep < 0)[0]   # Shared parameter indices

  # Check that output path exists:
  if savefile is not None:
      fpath, fname = os.path.split(os.path.realpath(savefile))
      if not os.path.exists(fpath):
          log.warning("Output folder path: '{:s}' does not exist. "
                      "Creating new folder.".format(fpath))
          os.makedirs(fpath)

  # Least-squares minimization:
  chisq_factor = 1.0
  if leastsq is not None:
      fit_output = fit(data, uncert, func, np.copy(params), indparams,
          pstep, pmin, pmax, prior, priorlow, priorup, leastsq)
      log.msg("Least-squares best-fitting parameters:\n  {}\n\n".
               format(fit_output['bestp']), si=2)

      # Scale data-uncertainties such that reduced chisq = 1:
      if chisqscale:
          chisq_factor = np.sqrt(fit_output['best_chisq']/(ndata-nfree))
          uncert *= chisq_factor

          # Re-calculate best-fitting parameters with new uncertainties:
          fit_output = fit(data, uncert, func, np.copy(params), indparams,
              pstep, pmin, pmax, prior, priorlow, priorup, leastsq)
          log.msg("Least-squares best-fitting parameters (rescaled chisq):"
                  "\n  {}\n\n".format(fit_output['bestp']), si=2)
      params = np.copy(fit_output['bestp'])
  else:
      fit_output = None

  if resume:
      with np.load(savefile) as oldrun:
          uncert *= float(oldrun['chisq_factor'])/chisq_factor
          chisq_factor = float(oldrun['chisq_factor'])

  # Here's where the magic happens:
  if sampler in ['mrw', 'demc', 'snooker']:
      output = mcmc(data, uncert, func, params, indparams, pmin, pmax, pstep,
          prior, priorlow, priorup, nchains, ncpu, nsamples, sampler,
          wlike, fit_output, grtest, grbreak, grnmin, burnin, thinning,
          fgamma, fepsilon, hsize, kickoff, savefile, resume, log)

  if leastsq is not None:
      if output['best_log_post']-fit_output['best_log_post'] < -3.0e-8:
          np.set_printoptions(precision=8)
          log.warning("MCMC found a better fit than the minimizer:\n"
              "MCMC best-fitting parameters:        (chisq={:.8g})\n{}\n"
              "Minimizer best-fitting parameters:   (chisq={:.8g})\n{}".
              format(output['best_log_post'], output['bestp'],
                  fit_output['best_log_post'], fit_output['bestp']))
      else:
          output['best_log_post'] = fit_output['best_log_post']
          output['best_chisq'] = fit_output['best_chisq']
          output['best_model'] = fit_output['best_model']
          output['bestp'] = fit_output['bestp']

  # And remove burn-in samples:
  posterior, zchain, zmask = mu.burn(Z=output['posterior'],
      zchain=output['zchain'], burnin=output['burnin'])

  # Get some stats:
  output['chisq_factor'] = chisq_factor
  output['BIC'] = output['best_chisq'] + nfree*np.log(ndata)
  if ndata > nfree:
      output['red_chisq'] = output['best_chisq']/(ndata-nfree)
  else:
      output['red_chisq'] = np.nan
  output['stddev_residuals'] = np.std(output['best_model']-data)

  # Compute the credible region for each parameter:
  bestp = output['bestp']
  CRlo = np.zeros(nparams)
  CRhi = np.zeros(nparams)
  pdf  = []
  xpdf = []
  for post, idx in zip(posterior.T, ifree):
      PDF, Xpdf, HPDmin = ms.cred_region(post)
      pdf.append(PDF)
      xpdf.append(Xpdf)
      CRlo[idx] = np.amin(Xpdf[PDF>HPDmin])
      CRhi[idx] = np.amax(Xpdf[PDF>HPDmin])
  # CR relative to the best-fitting value:
  CRlo[ifree] -= bestp[ifree]
  CRhi[ifree] -= bestp[ifree]

  # Get the mean and standard deviation from the posterior:
  meanp = np.zeros(nparams, np.double) # Parameters mean
  stdp  = np.zeros(nparams, np.double) # Parameter standard deviation
  meanp[ifree] = np.mean(posterior, axis=0)
  stdp [ifree] = np.std(posterior,  axis=0)
  for s in ishare:
      bestp[s] = bestp[-int(pstep[s])-1]
      meanp[s] = meanp[-int(pstep[s])-1]
      stdp [s] = stdp [-int(pstep[s])-1]
      CRlo [s] = CRlo [-int(pstep[s])-1]
      CRhi [s] = CRhi [-int(pstep[s])-1]

  output['CRlo'] = CRlo
  output['CRhi'] = CRhi
  output['stdp'] = stdp
  output['meanp'] = meanp

  log.msg("\nParam name     Best fit   Lo HPD CR   Hi HPD CR        Mean    Std dev       S/N"
          "\n----------- ----------------------------------- ---------------------- ---------", width=80)
  for i in range(nparams):
      snr  = "{:.1f}".   format(np.abs(bestp[i])/stdp[i])
      mean = "{: 11.4e}".format(meanp[i])
      lo   = "{: 11.4e}".format(CRlo[i])
      hi   = "{: 11.4e}".format(CRhi[i])
      if   i in ifree:  # Free-fitting value
          pass
      elif i in ishare: # Shared value
          snr = "[share{:02d}]".format(-int(pstep[i]))
      else:             # Fixed value
          snr = "[fixed]"
          mean = "{: 11.4e}".format(bestp[i])
      log.msg("{:<11s} {:11.4e} {:>11s} {:>11s} {:>11s} {:10.4e} {:>9s}".
              format(pnames[i][0:11], bestp[i], lo, hi, mean, stdp[i], snr),
              width=160)

  fmt = len("{:.4f}".format(output['BIC']))  # Length of string formatting
  log.msg(" ")
  if chisqscale:
      log.msg("sqrt(reduced chi-squared) factor: {:{}.4f}".
              format(output['chisq_factor'], fmt), indent=2)
  log.msg("Best-parameter's chi-squared:     {:{}.4f}".
          format(output['best_chisq'], fmt), indent=2)
  log.msg("Bayesian Information Criterion:   {:{}.4f}".
          format(output['BIC'], fmt), indent=2)
  log.msg("Reduced chi-squared:              {:{}.4f}".
          format(output['red_chisq'], fmt), indent=2)
  log.msg("Standard deviation of residuals:  {:.6g}\n".
          format(output['stddev_residuals']), indent=2)

  if savefile is not None or plots or closelog:
      log.msg("\nOutput sampler files:")

  # Save definitive results:
  if savefile is not None:
      np.savez(savefile, **output)
      log.msg("'{:s}'".format(savefile), indent=2)

  if plots:
      # Extract filename from savefile or default to sampler:
      fname = sampler if savefile is None else os.path.splitext(savefile)[0]
      # Include bestp in posterior plots:
      best_freepars = output['bestp'][ifree] if showbp else None

      # Trace plot:
      mp.trace(output['posterior'], zchain=output['zchain'],
          burnin=output['burnin'], pnames=texnames[ifree],
          savefile=fname+"_trace.png")
      log.msg("'{:s}'".format(fname+"_trace.png"), indent=2)
      # Pairwise posteriors:
      mp.pairwise(posterior, pnames=texnames[ifree], bestp=best_freepars,
          savefile=fname+"_pairwise.png")
      log.msg("'{:s}'".format(fname+"_pairwise.png"), indent=2)
      # Histograms:
      mp.histogram(posterior, pnames=texnames[ifree], bestp=best_freepars,
          savefile=fname+"_posterior.png",
          percentile=0.683, pdf=pdf, xpdf=xpdf)
      log.msg("'{:s}'".format(fname+"_posterior.png"), indent=2)
      # RMS vs bin size:
      if rms:
          RMS, RMSlo, RMShi, stderr, bs = ms.time_avg(output['best_model']-data)
          mp.rms(bs, RMS, stderr, RMSlo, RMShi, binstep=len(bs)//500+1,
                 savefile=fname+"_RMS.png")
          log.msg("'{:s}'".format(fname+"_RMS.png"), indent=2)
      # Sort of guessing that indparams[0] is the X array for data as in y=y(x):
      if (indparams != []
          and isinstance(indparams[0], (list, tuple, np.ndarray))
          and np.size(indparams[0]) == ndata):
          try:
              mp.modelfit(data, uncert, indparams[0], output['best_model'],
                  savefile=fname+"_model.png")
              log.msg("'{:s}'".format(fname+"_model.png"), indent=2)
          except:
              pass

  # Close the log file if necessary:
  if closelog:
      log.msg("'{:s}'".format(log.logname), indent=2)
      log.close()

  return output
