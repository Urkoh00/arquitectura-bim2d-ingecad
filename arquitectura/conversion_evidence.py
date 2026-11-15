# SPDX-License-Identifier: GPL-3.0-or-later
"""Narrow evidence adapters for the existing wall/geometry readers."""
from __future__ import annotations
import math
from .vendor import walldetect as W

TOL=.005


def recover_terminal_doors(walls,ops,reader):
    """A missing end opening requires both a crossing wall and a real swing.
    Extend only to the existing network, never to a guessed free endpoint.
    """
    walls=list(walls);ops=list(ops);count=0
    for k,(a,b,t) in enumerate(list(walls)):
        length=math.dist(a,b);u=W._unit_v(W._sub(b,a));ends=[a,b]
        for end,sign in ((0,-1),(1,1)):
            origin=(a,b)[end];candidates=[]
            for j,(c,d,t2) in enumerate(walls):
                if j==k:continue
                v=W._unit_v(W._sub(d,c));sine=abs(u[0]*v[1]-u[1]*v[0])
                if sine<.5:continue
                x=W._cross_pt(a,u,c,v)
                if x is None:continue
                beyond=sign*W._dot(W._sub(x,origin),u)
                along=W._dot(W._sub(x,c),v)
                if not 0< beyond <=W.OPEN_MAX+t2 or not -t<=along<=math.dist(c,d)+t:continue
                width=beyond-t2/(2*sine)
                if not W.OPEN_MIN<=width<=W.OPEN_MAX:continue
                mid=W._add(origin,W._mul(u,sign*width/2))
                evidence=reader.swings(mid,width,u,t)
                if evidence:
                    candidates.append((beyond,x,mid,width,evidence))
            if not candidates:continue
            distance,x,mid,width,((kind,hinge,side),attrs)=min(candidates,key=lambda x:x[0])
            if end==0:
                for z,o in enumerate(ops):
                    if o[0]==k:ops[z]=(k,o[1]+distance,*o[2:])
            ends[end]=x
            pos=W._dot(W._sub(mid,ends[0]),u)
            ops.append((k,pos,width,kind,hinge,side));reader.details[reader_key(mid,width)]=attrs;count+=1
        walls[k]=(ends[0],ends[1],t)
    return walls,ops,count


def reader_key(mid,width):
    from .conversion_openings import key
    return key(mid,width)


def exterior_side(walls,k,pos):
    """Interior sign from the existing canonical envelope, if unambiguous."""
    from .geom import junctions as J,spaces
    specs=[J.Wall(str(i),a,b,t,'eje')for i,(a,b,t)in enumerate(walls)]
    result=J.solve(specs);rings=[outer for outer,holes in spaces.components(result)]
    w=specs[k];a=w.point(pos,w.hi+.02);b=w.point(pos,w.lo-.02)
    inside=lambda p:any(spaces._inside(p,ring) for ring in rings)
    hi,lo=inside(a),inside(b)
    return 1 if hi and not lo else -1 if lo and not hi else None


def window_frame(reader,mid,width,u,t,interior=None):
    """Read a frame bounded at BOTH jambs, inside the wall band.

    An exterior sill can identify the side but never becomes the frame depth.
    Missing evidence is reported rather than treated as an exact flush fit.
    """
    n=W._perp(u);longs=[];caps=[];margin=max(.06,min(.15,.12*width))
    for segment,role in reader.lines:
        (a,y),(b,z)=[(W._dot(W._sub(p,mid),u),W._dot(W._sub(p,mid),n))for p in (segment[:2],segment[2:])]
        if min(a,b)<-width/2-margin or max(a,b)>width/2+margin:continue
        if abs(y-z)<TOL and abs(b-a)>=.65*width and max(abs(y),abs(z))<=t/2+.25:
            longs.append((min(a,b),max(a,b),(y+z)/2))
        if abs(a-b)<TOL and .015<=abs(z-y)<=t+TOL:
            lo,hi=sorted((y,z))
            if lo>=-t/2-TOL and hi<=t/2+TOL and abs(abs((a+b)/2)-width/2)<margin:
                caps.append(((a+b)/2,lo,hi))
    candidates=[]
    for x,lo,hi in caps:
        if not any(x*q<0 and abs(lo-l)<TOL and abs(hi-h)<TOL for q,l,h in caps):continue
        levels={round(y,5)for a,b,y in longs if lo-TOL<=y<=hi+TOL}
        if len(levels)>=2:candidates.append((hi-lo,-len(levels),lo,hi))
    if interior is None:
        outside_hi=any(y>t/2+.01 for a,b,y in longs)
        outside_lo=any(y<-t/2-.01 for a,b,y in longs)
        if outside_hi!=outside_lo:interior=-1 if outside_hi else 1
    attrs={}
    if candidates:
        depth,_,lo,hi=min(candidates)
        if interior is not None:
            attrs={'frame_depth':depth,'face':'distancia','setback_from':'exterior',
                   'setback':max(0.,lo+t/2 if interior>0 else t/2-hi)}
    return interior,attrs


def recover_short_links(walls,faces,tmin,tmax):
    """Keep a short paired return only if BOTH ends meet different walls."""
    result=list(walls);count=0
    raw=W._pairs(W._contiguous([(s[:2],s[2:4])for s in faces]),tmin,tmax,min_overlap=.025)
    for piece in raw:
        p,q,t=piece['p'],piece['q'],piece['t'];length=math.dist(p,q)
        if not max(.025,.1*t)<=length<max(W.MIN_RUN,1.5*t):continue
        u=W._unit_v(W._sub(q,p));n=W._perp(u)
        if any(abs(W._dot(W._sub(p,a),W._perp(W._unit_v(W._sub(b,a)))))<.01
               and abs(abs(W._dot(u,W._unit_v(W._sub(b,a))))-1)<.01
               and min(W._dot(W._sub(p,a),W._unit_v(W._sub(b,a))),W._dot(W._sub(q,a),W._unit_v(W._sub(b,a))))>=-.01
               and max(W._dot(W._sub(p,a),W._unit_v(W._sub(b,a))),W._dot(W._sub(q,a),W._unit_v(W._sub(b,a))))<=math.dist(a,b)+.01
               for a,b,tt in result):continue
        hits=[]
        for endpoint in (p,q):
            nearby=[]
            for i,(a,b,tt)in enumerate(result):
                v=W._unit_v(W._sub(b,a));sine=abs(u[0]*v[1]-u[1]*v[0])
                if sine<.5:continue
                x=W._cross_pt(p,u,a,v)
                if x is None:continue
                reach=(tt/2+t/2*abs(W._dot(u,v)))/sine+TOL
                along=W._dot(W._sub(x,a),v)
                if math.dist(x,endpoint)<=reach and -t/2-TOL<=along<=math.dist(a,b)+t/2+TOL:
                    nearby.append((math.dist(x,endpoint),i,x))
            hits.append(min(nearby)if nearby else None)
        if all(hits)and hits[0][1]!=hits[1][1]and math.dist(hits[0][2],hits[1][2])>=W.MIN_LEN:
            result.append((hits[0][2],hits[1][2],t));count+=1
    return result,count
