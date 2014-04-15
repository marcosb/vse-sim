from mydecorators import autoassign, cached_property, setdefaultattr
import random
from numpy.lib.scimath import sqrt
from numpy.core.fromnumeric import mean, std
from numpy.lib.function_base import median
from numpy.ma.core import floor
from test.test_binop import isnum

def debug(*args):
    if DEBUG:
        print(*args)

DEBUG = True

class Voter(tuple):
    """A tuple of candidate utilities.
    
    

    """
    
    @classmethod
    def rand(cls, ncand):
        """Create a random voter with standard normal utilities.
        
        ncand determines how many utilities a voter should have
            >>> [len(Voter.rand(i)) for i in list(range(5))]
            [0, 1, 2, 3, 4]
        
        utilities should be in a standard normal distribution
            >>> v100 = Voter.rand(100)
            >>> -0.3 < mean(v100) < 0.3
            True
            >>> 0.8 < std(v100) < 1.2
            True
        """
        return cls(random.gauss(0,1) for i in range(ncand))
        
    
    def hybridWith(self, v2, w2):
        """Create a weighted average of two voters. 
        
        The weight of v1 is always 1; w2 is the weight of v2 relative to that.
        
        If both are
        standard normal to start with, the result will be standard normal too.
        
        Length must be the same
            >>> Voter([1,2]).hybridWith(Voter([1,2,3]),1)
            Traceback (most recent call last):
              ...
            AssertionError

        A couple of basic sanity checks:
            >>> v2 = Voter([1,2]).hybridWith(Voter([3,2]),1)
            >>> [round(u,5) for u in v2.hybridWith(v2,1)]
            [4.0, 4.0]
            >>> Voter([1,2,5]).hybridWith(Voter([-0.5,-1,0]),0.75)
            (0.5, 1.0, 4.0)
        """
        assert len(self) == len(v2)
        return self.copyWithUtils(  ((self[i] / sqrt(1 + w2 ** 2)) + 
                                    (w2 * v2[i] / sqrt(1 + w2 ** 2)))
                                 for i in range(len(self)))
            
    def copyWithUtils(self, utils):
        """create a new voter with attrs as self and given utils.
        
        This version is a stub, since this voter class has no attrs."""
        return self.__class__(utils)
    
    def mutantChild(self, muteWeight):
        """Returns a copy hybridized with a random voter of weight muteWeight.
        
        Should remain standard normal:
            >>> v100 = Voter.rand(100)
            >>> for i in range(30):
            ...     v100 = v100.mutantChild(random.random())
            ... 
            >>> -0.3 < mean(v100) < 0.3 #3 sigma
            True
            >>> 0.8 < std(v100) < 1.2 #meh that's roughly 3 sigma
            True

        """
        return self.hybridWith(self.__class__.rand(len(self)), muteWeight)
    
class PersonalityVoter(Voter):
    
    cluster_count = 0
    
    def __init__(self, *args, **kw):
        super().__init__()#*args, **kw) #WTF, python?
        self.cluster = self.__class__.cluster_count
        self.__class__.cluster_count += 1
        self.personality = random.gauss(0,1) #probably to be used for strategic propensity
        #but in future, could be other clustering voter variability, such as media awareness
        #print(self.cluster, self.personality)
        
    #@classmethod
    #def rand(cls, ncand):
    #    voter = super().rand(ncand)
    #    return voter
    
    @classmethod
    def resetClusters(cls):
        cls.cluster_count = 0
    
    def copyWithUtils(self, utils):
        voter = super().copyWithUtils(utils)
        voter.personality = self.personality
        voter.cluster = self.cluster
        return voter
            
class Electorate(list):
    """A list of voters.
    Each voter is a list of candidate utilities"""
    @cached_property
    def socUtils(self):
        """Just get the social utilities.
        
        >>> e = Electorate([[1,2],[3,4]])
        >>> e.socUtils
        [2.0, 3.0]
        """
        return list(map(mean,zip(*self)))
    
class RandomModel:
    """Empty base class for election models; that is, electorate factories.
    
    >>> e4 = RandomModel()(4,3)
    >>> [len(v) for v in e4]
    [3, 3, 3, 3]
    """
    def __call__(self, nvot, ncand, vType=PersonalityVoter):
        return Electorate(vType.rand(ncand) for i in range(nvot))
    
class DeterministicModel:
    """Basically, a somewhat non-boring stub for testing.
    
        >>> DeterministicModel(3)(4, 3)
        [(0, 1, 2), (1, 2, 0), (2, 0, 1), (0, 1, 2)]
    """
    
    @autoassign
    def __init__(self, modulo):
        pass
    
    def __call__(self, nvot, ncand, vType=PersonalityVoter):
        return Electorate(vType((i+j)%self.modulo for i in range(ncand))
                          for j in range(nvot))
    
class ReverseModel(RandomModel):
    """Creates an even number of voters in two diametrically-opposed camps
    (ie, opposite utilities for all candidates)
    
    >>> e4 = ReverseModel()(4,3)
    >>> [len(v) for v in e4]
    [3, 3, 3, 3]
    >>> e4[0].hybridWith(e4[3],1)
    (0.0, 0.0, 0.0)
    """
    def __call__(self, nvot, ncand, vType=PersonalityVoter):
        if nvot % 2:
            raise ValueError
        basevoter = vType.rand(ncand)
        return Electorate( ([basevoter] * (nvot//2)) + 
                           ([vType(-q for q in basevoter)] * (nvot//2))
                        )

class QModel(RandomModel):
    """Adds a quality dimension to a base model,
    by generating an election and then hybridizing all voters
    with a common quality vector.
    
    Useful along with ReverseModel to create a poor-man's 2d model.
    
    Basic structure
        >>> e4 = QModel(sqrt(3), RandomModel())(100,1)
        >>> len(e4)
        100
        >>> len(e4.socUtils)
        1
        
    Reduces the standard deviation
        >>> 0.4 < std(list(zip(e4))) < 0.6
        True

    """
    @autoassign
    def __init__(self, qWeight=0.5, baseModel=ReverseModel()):
        pass
    
    def __call__(self, nvot, ncand, vType=PersonalityVoter):
        qualities = vType.rand(ncand)
        return Electorate([v.hybridWith(qualities,self.qWeight)
                for v in self.baseModel(nvot, ncand, vType)])


class PolyaModel(RandomModel):
    """This creates electorates based on a Polya/Hoppe/Dirchlet model, with mutation.
    You start with an "urn" of n=seedVoter voters from seedModel,
     plus alpha "wildcard" voters. Then you draw a voter from the urn, 
     clone and mutate them, and put the original and clone back into the urn.
     If you draw a "wildcard", use voterGen to make a new voter.
     """
    @autoassign
    def __init__(self, seedVoters=2, alpha=1, seedModel=QModel(),
                 mutantFactor=0.2):
        pass
    
    def __call__(self, nvot, ncand, vType=PersonalityVoter):
        """Tests? Making statistical tests that would pass reliably is
        a huge hassle. Sorry, maybe later.
        """
        vType.resetClusters()
        election = self.seedModel(self.seedVoters, ncand, vType)
        while len(election) < nvot:
            i = random.randrange(len(election) + self.alpha)
            if i < len(election):
                election.append(election[i].mutantChild(self.mutantFactor))
            else:
                election.append(vType.rand(ncand))
        return election





###################Choosers
class Chooser:
    tallyKeys = []
    
    @autoassign
    def __init__(self, choice, name=None, subChoosers=[]):
        """Subclasses should just copy/paste this logic because
        each will have its own parameters and so that's easiest."""
        pass
        
    def getName(self):
        if hasattr(self, "choice"): #only true for base class
            return self.choice
        if not hasattr(self, "name") or not self.name:
            self.name = self.__class__.__name__[:-7] #drop the "Chooser"
        return self.name
    
    def __call__(self, cls, voter, tally):
        return self.choice
            
    def addTallyKeys(self, tally):
        for key in self.allTallyKeys:
            tally[key] = 0
            
    @cached_property
    def myKeys(self):
        prefix = self.getName() + "_"
        return [prefix + key for key in self.tallyKeys]
    
    @cached_property
    def allTallyKeys(self):
        keys = self.getMyKeys()
        for subChooser in self.subChoosers:
            keys += subChooser.getTallyKeys()
        return keys
    
    @cached_property
    def __name__(self):
        return self.__class__.__name__

beHon = Chooser("hon")
beStrat = Chooser("strat")
beX = Chooser("extraStrat")

class LazyChooser(Chooser):
    tallyKeys = [""] 
    @autoassign
    def __init__(self, name=None, subChoosers=[beHon, beX]):
        pass
    
    
    def __call__(self, cls, voter, tally):
        if (getattr(voter, cls.__name__ + "_hon") ==
            getattr(voter, cls.__name__ + "_strat")):
            tally[self.myKeys[0]] += 0
            return self.subChoosers[0](cls, voter, tally) #hon
        tally[self.myKeys[0]] += 1
        return self.subChoosers[1](cls, voter, tally) #strat

class OssChooser(Chooser):
    tallyKeys = [""] 
    """one-sided strategy:
    returns a 'strategic' ballot for those who prefer the honest runner-up,
    and an honest ballot for those who prefer the honest winner. Only works
    if honBallot and stratBallot have already been called for the voter.
    
    
    """
    @autoassign
    def __init__(self, name=None, subChoosers = [beHon, beStrat]):
        pass
    
    def __call__(self, cls, voter, tally):
        hon, strat = self.subChoosers
        if getattr(voter, cls.__name__ + "_isStrat", False):
            if callable(strat):
                debug(strat)
                return strat(cls, voter, tally)
            tally[self.myKeys[0]] += 1
            return strat
        else:
            if callable(hon):
                debug(hon)
                return hon(cls, voter, tally)
            return hon


class ProbChooser(Chooser):
    @autoassign
    def __init__(self, probs, name=None):
        self.subChoosers = [chooser for (p, chooser) in probs]
    
    def __call__(self, cls, voter, tally):
        r = random.random()
        for (i, (p, chooser)) in enumerate(self.probs):
            r -= p
            if r < 0:
                if i > 0: #keep tally for all but first option
                    tally[self.getName() + "_" + chooser.getName()] += 1
                return chooser(cls, voter, tally)
    
    
    
    
    
###media

def truth(standings, tally=None):
    return standings

def topNMediaFor(n, tally=None):
    def topNMedia(standings):
        return list(standings[:n]) + [min(standings)] * (len(standings) - n)
    return topNMedia

def biaserAround(scale):
    def biaser(standings):
        return scale * (max(standings) - min(standings))
    
def orderOf(standings):
    return [i for i,val in sorted(list(enumerate(standings)), key=lambda x:x[1], reverse=True)]

def biasedMediaFor(biaser=biaserAround(0.367879)): 
            #Ludicrous precision, only to show that I've arbitrarily picked 1/e
            #which is an arbitrary compromise between 1/3 and 1/2
    """
    0, 0, -1/2, -2/3, -4/5....
    """
    def biasedMedia(standings, tally=None):
        if not tally:
            tally=SideTally()
        if callable(biaser):
            bias = biaser(standings)
        else:
            bias = biaser
        result= [(standing - bias + (bias / max(i, 1))) for i, standing in enumerate(standings)]
        tally["changed"] += 0 if orderOf(result)[0:2] == orderOf(standings)[0:2] else 1
        return result
    return biasedMedia

def skewedMediaFor(biaser):
    """
    
    [0, -1/3, -2/3, -1]
    """
    def skewedMedia(standings, tally=None):
        if not tally:
            tally=SideTally()
        if callable(biaser):
            bias = biaser(standings)
        else:
            bias = biaser
        result= [(standing - bias * i / (len(standings) - 1)) for i, standing in enumerate(standings)]
        
        tally["changed"] += 0 if orderOf(result)[0:2] == orderOf(standings)[0:2] else 1
        return result
    return skewedMedia




####data holders for output
from collections import defaultdict
class SideTally(defaultdict):
    """Used for keeping track of how many voters are being strategic, etc.
    
    DO NOT use plain +; for this class, it is equivalent to +=, but less readable.
    
    """
    def __init__(self):
        super().__init__(int)
    #>>> tally = SideTally()
    #>>> tally += {1:2,3:4}
    #>>> tally
    #{1: 2, 3: 4}
    #>>> tally += {1:2,3:4,5:6}
    #>>> tally
    #{1: 4, 3: 8, 5: 6}
    #"""
    #def __add__(self, other):
    #    for (key, val) in other.items():
    #        try:
    #            self[key] += val
    #        except KeyError:
    #            self[key] = val
    #    return self
    
    def initKeys(self, chooser):
        try:
            self.keyList = chooser.allTallyKeys()
        except AttributeError:
            try:
                self.keyList = list(chooser)
            except TypeError:
                debug("Chooser has no tally keys:", chooser)
        self.initKeys = staticmethod(lambda x:x) #don't do it again
    
    def serialize(self):
        try:
            return [self[key] for key in self.keyList]
        except AttributeError:
            return []
        
    def fullSerialize(self):
        try:
            return [self[key] for key in self.keys()]
        except AttributeError:
            return []
    
class Tallies(list):
    """Used (ONCE) as an enumerator, gives an inexhaustible flow of SideTally objects.
    After that, use as list to see those objects.
    
    >>> ts = Tallies()
    >>> for i, j in zip(ts, [5,4,3]):
    ...     i[j] += j
    ... 
    >>> [t.serialize() for t in ts]
    [[], [], [], []]
    >>> [t.fullSerialize() for t in ts]
    [[5], [4], [3], []]
    >>> [t.initKeys([k]) for (t,k) in zip(ts,[6,4,3])]
    [None, None, None]
    >>> [t.serialize() for t in ts]
    [[0], [4], [3], []]
    """
    def __iter__(self):
        try:
            self.used
            return super().__iter__()
        except:
            self.used = True
            return self
    
    def __next__(self):
        tally = SideTally()
        self.append(tally)
        return tally
                
class VseOneRun:
    @autoassign
    def __init__(self, result, tally, strat):
        pass

class VseMethodRun:
    @autoassign
    def __init__(self, method, choosers, results):
        pass
    

##Election Methods
class Method:
    """Base class for election methods. Holds some of the duct tape."""
        
    def results(self, ballots):
        """Combines ballots into results. Override for comparative
        methods.
        
        Test for subclasses, makes no sense to test this method in the abstract base class.
        """
        if type(ballots) is not list:
            ballots = list(ballots)
        return list(map(self.candScore,zip(*ballots)))
    
    @staticmethod
    def winner(results):
        """Simply find the winner once scores are already calculated. Override for
        ranked methods.
        

        >>> Method().winner([1,2,3,2,-100])
        2
        >>> 2 < Method().winner([1,2,1,3,3,3,2,1,2]) < 6
        True
        """
        winScore = max([result for result in results if isnum(result)])
        winners = [cand for (cand, score) in enumerate(results) if score==winScore]
        return random.choice(winners)
    
    def resultsFor(self, voters, chooser, tally=None):
        """create ballots and get results. 
        
        Again, test on subclasses.
        """
        if tally is None:
            tally = SideTally()
        tally.initKeys(chooser)
        return (self.results(chooser(self.__class__, voter, tally) 
                                  for voter in voters), chooser.__name__)
        
    def multiResults(self, voters, chooserFuns=(), media=lambda x,t:x):
        """Runs two base elections: first with honest votes, then
        with strategic results based on the first results (filtered by
        the media). Then, runs a series of elections using each chooserFun
        in chooserFuns to select the votes for each voter.
        
        Returns a tuple of (honResults, stratResults, ...). The stratresults
        are based on common information, which is given by media(honresults).
        """
        honTally = SideTally()
        hon = self.resultsFor(voters, self.honBallot, honTally)
        stratTally = SideTally()
        info = media(hon[0], stratTally)
        strat = self.resultsFor(voters, self.stratBallotFor(info), stratTally)
        extraTallies = Tallies()
        extras = [self.resultsFor(voters, self.ballotChooserFor(chooserFun))
                  for (chooserFun, aTally) in zip(chooserFuns, extraTallies)]
        return ([(hon, honTally), (strat, stratTally)] + 
                list(zip(extras, list(extraTallies))))
        
    def vseOn(self, voters, chooserFuns=(), **args):
        """Finds honest and strategic voter satisfaction efficiency (VSE) 
        for this method on the given electorate.
        """
        multiResults = self.multiResults(voters, chooserFuns, **args)
        utils = voters.socUtils
        best = max(utils)
        rand = mean(utils)
        
        vses = VseMethodRun(self.__class__, chooserFuns,
                    [VseOneRun([(utils[self.winner(result)] - rand) / (best - rand)],tally,chooser)
                        for ((result, chooser), tally) in multiResults])
        return vses
    
    @staticmethod
    def ballotChooserFor(chooserFun):
        """Takes a chooserFun; returns a ballot chooser using that chooserFun
        """
        def ballotChooser(cls, voter, tally):
            return getattr(voter, cls.__name__ + "_" + chooserFun(cls, voter, tally))
        ballotChooser.__name__ = chooserFun.__name__
        return ballotChooser

def rememberBallot(fun):
    """A decorator for a function of the form xxxBallot(cls, voter)
    which memoizes the vote onto the voter in an attribute named <methName>_xxx
    """
    def getAndRemember(cls, voter, tally=None):
        ballot = fun(cls, voter)
        setattr(voter, cls.__name__ + "_" + fun.__name__[:-6], ballot) #leave off the "...Ballot" 
        return ballot
    getAndRemember.__name__ = fun.__name__
    return getAndRemember

def rememberBallots(fun):
    """A decorator for a function of the form xxxBallot(cls, voter)
    which memoizes the vote onto the voter in an attribute named <methName>_xxx
    """
    def getAndRemember(cls, voter, tally=None):
        ballots = fun(cls, voter)
        for bType, ballot in ballots.items():
            setattr(voter, cls.__name__ + "_" + bType, ballot) 
        
        return ballots[fun.__name__[:-6]] #leave off the "...Ballot" 
    getAndRemember.__name__ = fun.__name__
    return getAndRemember

####EMs themeselves
class Plurality(Method):
    
    #>>> pqs = [Plurality().resultsFor(PolyaModel()(101,5),Plurality.honBallot)[0] for i in range(400)]
    #>>> mean(pqs)
    #0.20534653465346522
    #>>> std(pqs)
    #0.2157069704671751
    bias = 0.2157069704671751
    
    candScore = staticmethod(mean)
    
    @staticmethod
    def oneVote(utils, forWhom):
        ballot = [0] * len(utils)
        ballot[forWhom] = 1
        return ballot
    
    @staticmethod #cls is provided explicitly, not through binding
    @rememberBallot
    def honBallot(cls, utils):
        """Takes utilities and returns an honest ballot
        
        >>> Plurality.honBallot(Plurality, Voter([-3,-2,-1]))
        [0, 0, 1]
        >>> Plurality().stratBallotFor([3,2,1])(Plurality, Voter([-3,-2,-1]))
        [0, 1, 0]
        """
        return cls.oneVote(utils, cls.winner(utils))
    
    def stratBallotFor(self, info):
        """Returns a (function which takes utilities and returns a strategic ballot)
        for the given "polling" info.
        
        >>> Plurality().stratBallotFor([3,2,1])(Plurality, Voter([-3,-2,-1]))
        [0, 1, 0]
        """ 
        
        places = sorted(enumerate(info),key=lambda x:-x[1]) #from high to low
        #print("placesxx",places)
        @rememberBallots
        def stratBallot(cls, voter):
            
            stratGap = voter[places[1][0]] - voter[places[0][0]]
            if stratGap <= 0:
                #winner is preferred; be complacent.
                isStrat = False
                strat = cls.oneVote(voter, places[0][0])
            else:
                #runner-up is preferred; be strategic in iss run
                isStrat = True
                #sort cuts high to low
                #cuts = (cuts[1], cuts[0])
                strat = cls.oneVote(voter, places[1][0])
            return dict(strat=strat, isStrat=isStrat, stratGap=stratGap)
        return stratBallot

class Score(Method): 
    """Score voting, 0-10.
    
    
    Strategy establishes pivots
        >>> Score().stratBallotFor([0,1,2])(Score, Voter([5,6,7]))
        [0, 0, 10]
        >>> Score().stratBallotFor([2,1,0])(Score, Voter([5,6,7]))
        [0, 10, 10]
        >>> Score().stratBallotFor([1,0,2])(Score, Voter([5,6,7]))
        [0, 5.0, 10]
        
    Strategy (kinda) works for ties
        >>> Score().stratBallotFor([1,0,2])(Score, Voter([5,6,6]))
        [0, 10, 10]
        >>> Score().stratBallotFor([1,0,2])(Score, Voter([6,6,7]))
        [0, 0, 10]
        >>> Score().stratBallotFor([1,0,2])(Score, Voter([6,7,6]))
        [10, 10, 10]
        >>> Score().stratBallotFor([1,0,2])(Score, Voter([6,5,6]))
        [10, 0, 10]

    """
    
    #>>> qs += [Score().resultsFor(PolyaModel()(101,2),Score.honBallot)[0] for i in range(800)]
    #>>> std(qs)
    #2.770135393419682
    #>>> mean(qs)
    #5.1467202970297032
    bias2 = 2.770135393419682
    #>>> qs5 = [Score().resultsFor(PolyaModel()(101,5),Score.honBallot)[0] for i in range(400)]
    #>>> mean(qs5)
    #4.920247524752476
    #>>> std(qs5)
    #2.3536762480634343
    bias5 = 2.3536762480634343
    
    candScore = staticmethod(mean)
        #"""Takes the list of votes for a candidate; returns the candidate's score."""

    @staticmethod #cls is provided explicitly, not through binding
    @rememberBallot
    def honBallot(cls, utils):
        """Takes utilities and returns an honest ballot (on 0..10)
        
        
        honest ballots work as expected
            >>> Score().honBallot(Score, Voter([5,6,7]))
            [0.0, 5.0, 10.0]
            >>> Score().resultsFor(DeterministicModel(3)(5,3),Score().honBallot)
            [4.0, 6.0, 5.0]
        """
        bot = min(utils)
        scale = max(utils)-bot
        return [floor(10.99 * (util-bot) / scale) for util in utils]
    
    def stratBallotFor(self, info):
        """Returns a (function which takes utilities and returns a strategic ballot)
        for the given "polling" info.""" 
        
        places = sorted(enumerate(info),key=lambda x:-x[1]) #from high to low
        #print("placesxx",places)
        @rememberBallots
        def stratBallot(cls, voter):
            cuts = [voter[places[0][0]], voter[places[1][0]]]
            stratGap = cuts[1] - cuts[0]
            if stratGap <= 0:
                #winner is preferred; be complacent.
                isStrat = False
            else:
                #runner-up is preferred; be strategic in iss run
                isStrat = True
                #sort cuts high to low
                cuts = (cuts[1], cuts[0])
            if cuts[0] == cuts[1]:
                strat = [(10 if (util >= cuts[0]) else 0) for util in voter]
            else:
                strat = [max(0,min(10,floor(
                                10.99 * (util-cuts[1]) / (cuts[0]-cuts[1])
                            ))) 
                        for util in voter]
            return dict(strat=strat, isStrat=isStrat, stratGap=stratGap)
        return stratBallot
    
    

def toVote(cutoffs, util):
    """maps one util to a vote, using cutoffs.
    
    Used by Mav, but declared outside to avoid method binding overhead."""
    for vote in range(len(cutoffs)):
        if util <= cutoffs[vote]:
            return vote
    return vote + 1
    

class Mav(Method):
    """Majority Approval Voting
    """
    
    
    #>>> mqs = [Mav().resultsFor(PolyaModel()(101,5),Mav.honBallot)[0] for i in range(400)]
    #>>> mean(mqs)
    #1.5360519801980208
    #>>> mqs += [Mav().resultsFor(PolyaModel()(101,5),Mav.honBallot)[0] for i in range(1200)]
    #>>> mean(mqs)
    #1.5343069306930679
    #>>> std(mqs)
    #1.0970202515275356
    bias5 = 1.0970202515275356

    
    baseCuts = [-0.8, 0, 0.8, 1.6]
    def candScore(self, scores):
        """For now, only works correctly for odd nvot
        
        Basic tests
            >>> Mav().candScore([1,2,3,4,5])
            3.0
            >>> Mav().candScore([1,2,3,3,3])
            2.5
            >>> Mav().candScore([1,2,3,4])
            2.5
            >>> Mav().candScore([1,2,3,3])
            2.5
            >>> Mav().candScore([1,2,2,2])
            1.5
            >>> Mav().candScore([1,2,3,3,5])
            2.7
            """
        scores = sorted(scores)
        nvot = len(scores)
        nGrades = (len(self.baseCuts) + 1)
        i = int((nvot - 1) / 2)
        base = scores[i]
        while (i < nvot and scores[i] == base):
            i += 1
        upper =  (base + 0.5) - (i - nvot/2) * nGrades / nvot
        lower = (base) - (i - nvot/2) / nvot
        return max(upper, lower)
    
    @staticmethod #cls is provided explicitly, not through binding
    @rememberBallot
    def honBallot(cls, voter):
        """Takes utilities and returns an honest ballot (on 0..4)

        honest ballot works as intended, gives highest grade to highest utility:
            >>> Mav().honBallot(Mav, Voter([-1,-0.5,0.5,1,1.1]))
            3
            [0, 1, 2, 3, 4]
            
        Even if they don't rate at least an honest "B":
            >>> Mav().honBallot(Mav, Voter([-1,-0.5,0.5]))
            [0, 1, 4]
        """
        cutoffs = [min(cut, max(voter) - 0.001) for cut in cls.baseCuts]
        return [toVote(cutoffs, util) for util in voter]
        
    
    def stratBallotFor(self, info):
        """Returns a function which takes utilities and returns a dict(
            strat=<ballot in which all grades are exaggerated 
                             to outside the range of the two honest frontrunners>,
            extraStrat=<ballot in which all grades are exaggerated to extremes>,
            isStrat=<whether the runner-up is preferred to the frontrunner (for reluctantStrat)>,
            stratGap=<utility of runner-up minus that of frontrunner>
            )
        for the given "polling" info.
        
        
        
        Strategic tests:
            >>> Mav().stratBallotFor([0,1.1,1.9,0,0])(Mav, Voter([-1,-0.5,0.5,1,2]))
            [0, 1, 2, 3, 4]
            >>> Mav().stratBallotFor([0,2.1,2.9,0,0])(Mav, Voter([-1,-0.5,0.5,1,2]))
            [0, 1, 3, 3, 4]
            >>> Mav().stratBallotFor([0,2.1,1.9,0,0])(Mav, Voter([-1,0.4,0.5,1,2]))
            [0, 1, 3, 3, 4]
            >>> Mav().stratBallotFor([1,0,2])(Mav, Voter([6,7,6]))
            [4, 4, 4]
            >>> Mav().stratBallotFor([1,0,2])(Mav, Voter([6,5,6]))
            [4, 0, 4]
            >>> Mav().stratBallotFor([2.1,0,3])(Mav, Voter([6,5,6]))
            [4, 0, 4]
            >>> Mav().stratBallotFor([2.1,0,3])(Mav, Voter([6,5,6.1]))
            [2, 2, 4]
        """ 
        places = sorted(enumerate(info),key=lambda x:-x[1]) #from high to low
        #print("places",places)
        front = (places[0][0], places[1][0], places[0][1], places[1][1])
        
        @rememberBallots
        def stratBallot(cls, voter):
            frontUtils = [voter[front[0]], voter[front[1]]] #utils of frontrunners
            stratGap = frontUtils[1] - frontUtils[0]
            if stratGap is 0:
                strat = extraStrat = [(4 if (util >= frontUtils[0]) else 0)
                                     for util in voter]
                isStrat = True
                
            else:
                if stratGap < 0:
                    #winner is preferred; be complacent.
                    isStrat = False
                else:
                    #runner-up is preferred; be strategic in iss run
                    isStrat = True
                    #sort cuts high to low
                    frontUtils = (frontUtils[1], frontUtils[0])
                top = max(voter)
                cutoffs = [(  (min(frontUtils[0], self.baseCuts[i])) 
                                 if (i < floor(front[3])) else 
                            ( (frontUtils[1]) 
                                 if (i < floor(front[2]) + 1) else
                              min(top, self.baseCuts[i])
                              ))
                           for i in range(4)]
                strat = [toVote(cutoffs, util) for util in voter]
                extraStrat = [max(0,min(10,floor(
                                4.99 * (util-frontUtils[1]) / (frontUtils[0]-frontUtils[1])
                            ))) 
                        for util in voter]
            return dict(strat=strat, extraStrat=extraStrat, isStrat=isStrat,
                        stratGap = stratGap)
        return stratBallot
        
        
class Mj(Mav):
    def candScore(self, scores):
        """This formula will always give numbers within 0.5 of the raw median.
        Unfortunately, with 5 grade levels, these will tend to be within 0.1 of
        the raw median, leaving scores further from the integers mostly unused.
        This is only a problem aesthetically.
        
        For now, only works correctly for odd nvot
        
        tests:
            >>> Mj().candScore([1,2,3,4,5])
            3
            >>> Mj().candScore([1,2,3,3,5])
            2.7
            >>> Mj().candScore([1,3,3,3,5])
            3
            >>> Mj().candScore([1,3,3,4,5])
            3.3
            >>> Mj().candScore([1,3,3,3,3])
            2.9
            >>> Mj().candScore([3] * 24 + [1])
            2.98
            >>> Mj().candScore([3] * 24 + [4])
            3.02
            >>> Mj().candScore([3] * 13 + [4] * 12)
            3.46
            """
        scores = sorted(scores)
        nvot = len(scores)
        lo = hi = mid = nvot // 2
        base = scores[mid]
        while (hi < nvot and scores[hi] == base):
            hi += 1
        while (lo >= 0 and scores[lo] == base):
            lo -= 1
            
        if (hi-mid) == (mid-lo):
            return base
        elif (hi-mid) < (mid-lo):
            return base + 0.5 - (hi-mid) / nvot
        else:
            return base - 0.5 + (mid-lo) / nvot
        
class Irv(Method):
    
    #>>> iqs = [Irv().resultsFor(PolyaModel()(101,5),Irv.honBallot)[0] for i in range(400)]
    #>>> mean(iqs)
    #1.925
    #>>> std(iqs)
    #1.4175242502334846
    bias5 = 1.4175242502334846

    def resort(self, ballots, loser, ncand, piles):
        """No error checking; only works for exhaustive ratings."""
        #print("resort",ballots, loser, ncand)
        #print(piles)
        for ballot in ballots:
            if loser < 0:
                nextrank = ncand - 1
            else:
                nextrank = ballot[loser] - 1
            while 1:
                try:
                    piles[ballot.index(nextrank)].append(ballot)
                    break
                except AttributeError:
                    nextrank -= 1
                    if nextrank < 0:
                        raise
            
    def results(self, ballots):
        """IRV results.
        
        >>> Irv().resultsFor(DeterministicModel(3)(5,3),Irv().honBallot)[0]
        [0, 1, 2]
        >>> Irv().results([[0,1,2]])[2]
        2
        >>> Irv().results([[0,1,2],[2,1,0]])[1]
        0
        >>> Irv().results([[0,1,2]] * 4 + [[2,1,0]] * 3 + [[1,2,0]] * 2)
        [2, 0, 1]
        """
        if type(ballots) is not list:
            ballots = list(ballots)
        ncand = len(ballots[0])
        results = [-1] * ncand
        piles = [[] for i in range(ncand)]
        loserpile = ballots
        loser = -1
        for i in range(ncand):
            self.resort(loserpile, loser, ncand, piles)
            negscores = ["x" if isnum(pile) else -len(pile)
                         for pile in piles]
            loser = self.winner(negscores)
            results[loser] = i 
            loserpile, piles[loser] = piles[loser], -1
        return results
        
            
    @staticmethod #cls is provided explicitly, not through binding
    @rememberBallot
    def honBallot(cls, voter):
        """Takes utilities and returns an honest ballot
        
        >>> Irv.honBallot(Irv,Voter([4,1,6,3]))
        [2, 0, 3, 1]
        """
        ballot = [-1] * len(voter)
        order = sorted(enumerate(voter), key=lambda x:x[1])
        for i, cand in enumerate(order):
            ballot[cand[0]] = i
        return ballot
        
    
    def stratBallotFor(self, info):
        """Returns a function which takes utilities and returns a dict(
            isStrat=
        for the given "polling" info.
        
        
        >>> Irv().stratBallotFor([3,2,1,0])(Irv,Voter([3,6,5,2]))
        [1, 2, 3, 0]
        """ 
        ncand = len(info)
        
        places = sorted(enumerate(info),key=lambda x:-x[1]) #high to low
        @rememberBallots
        def stratBallot(cls, voter):
            stratGap = voter[places[1][0]] - voter[places[0][0]]
            if stratGap < 0:
                #winner is preferred; be complacent.
                isStrat = False
            else:
                #runner-up is preferred; be strategic in iss run
                isStrat = True
                #sort cuts high to low #NOT FOR IRV
                #places = (places[1], places[0])
            i = ncand - 1
            winnerQ = voter[places[0][0]]
            ballot = [-1] * len(voter)
            for nextLoser, loserScore in places[::-1][:-1]:
                if voter[nextLoser] > winnerQ:
                    ballot[nextLoser] = i
                    i -= 1
            ballot[places[0][0]] = i
            i -= 1
            for nextLoser, loserScore in places[1:]:
                if voter[nextLoser] <= winnerQ:
                    ballot[nextLoser] = i
                    i -= 1
            assert(i == -1)
            return dict(strat=ballot, isStrat=isStrat, stratGap=stratGap)
        return stratBallot
        
        
        
        
        
##Outer duct tape
class VseBatch:
    
    def __init__(self, model, methods, nvot, ncand, niter):
        """A harness function which creates niter elections from model and finds three kinds
        of VSE for all methods given.
        
        for instance:
        vses = VseBatch(PolyaModel(), [[Score(), baseRuns], [Mav(), medianRuns]], nvot=5, ncand=4, niter=3)
        
        >>> vses = VseBatch(PolyaModel(), [[Score(), baseRuns], [Mav(), medianRuns]], nvot=5, ncand=4, niter=3)
        >>> [[len(y) for y in x] for x in [vses.methods, vses.vses]]
        [[2, 2], [2, 2, 2]]
        """
        vses = []
        for i in range(niter):
            electorate = model(nvot, ncand)
            vse = []
            for method, chooserFuns in methods:
                vse.append(method.vseOn(electorate, chooserFuns))
            vses.append(vse)
            debug(i,vse)
        self.methods = methods
        self.vses = vses
                
    def printMe(self, comparisons):
        """print the result of doVse in an accessible format.
        for instance:
        printVse(vses)
        
        """
        for i in range(len(self.methods)):
            print(self.methods[i][0])
            print([strat for strat in self.methods[i][1]], 
                  [mean([result[i][j] for result in self.vses]) 
                      for j in range(len(self.methods[0]) - 1)],
                  mean(
                       [(0 if result[i][0]==result[i][2] else 1)
                            for result in self.vses]
                       )
                  )
            
    def save(self, fn="vseresults.txt"):
        
        out = open(fn, "wb")
        head, body = self.methods, self.vses
        lines = []
        headItems = []
        for meth, choosers in head:
            mname = meth.__class__.__name__
            headItems.extend([mname + "_hon",
                             mname + "_strat"])
            for i, chooser in enumerate(choosers):
                headItems.append("_".join(mname, chooser.getName()))
                for tallyKey in chooser.allTallyKeys():
                    headItems.append("_".join(mname, str(i), tallyKey))
            headItems.append(mname + "_strat_push")
            for i, xtra in enumerate(meth[1]):
                headItems.append(mname + "_" + xtra.__name__ + str(i) + "_push")
            
                
        lines.append("\t".join([str(item) for item in headItems]) + "\n")
        
        for line in body:
            lineItems = []
            for meth in line:
                lineItems.extend(meth[:-1])
            lines.append("\t".join(str(item) for item in lineItems) + "\n")
        
        for line in lines:
            out.write(bytes(line, 'UTF-8'))
        out.close()
        
    def printElection(self, e, output=print):
        for voter in e:
            output(voter[0], voter[1], voter.cluster)
            
    def saveNElections(self, n,model=PolyaModel(),nvot=101,ncand=2,basePath="/Users/chema/mydev/br/election"):
        f = None
        def writeToFile(*args):
            f.write(bytes("\t".join(str(arg) for arg in args) + "\n", 'UTF-8'))
        for i in range(n):
            e = model(nvot,ncand)
            f = open(basePath + str(i) + ".txt", "wb")
            self.printElection(e,writeToFile)
            f.close()
            
    
medianRuns = [OssChooser(), 
               OssChooser([beHon,ProbChooser([(1/2, beStrat), (1/2, beHon)])]), 
               
               
               ProbChooser([(1/4, beX), (3/4, beHon)]), 
               ProbChooser([(1/2, beX), (1/2, beHon)]), 
               ProbChooser([(3/4, beX), (1/4, beHon)]), 
               
               ProbChooser([(0.5, beStrat), (0.5, beHon)]), 
               ProbChooser([(1/3, beStrat), (1/3, beHon), (1/3, beX)]),
               
               LazyChooser(), 
               ProbChooser([(1/2, LazyChooser()), (1/2, beHon)]), 
               
               ]

baseRuns = [OssChooser(), 
           OssChooser([beHon,ProbChooser([(1/2, beStrat), (1/2, beHon)])]), 
           
           ProbChooser([(1/4, beStrat), (3/4, beHon)]), 
           ProbChooser([(1/2, beStrat), (1/2, beHon)]), 
           ProbChooser([(3/4, beStrat), (1/4, beHon)]), 
           
           ]

if __name__ == "__main__":
    import doctest
    DEBUG = False
    doctest.testmod()