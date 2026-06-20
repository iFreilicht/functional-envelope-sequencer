# Functional Envelope Sequencer

This purpose of this project is to develop and expirment with a novel approach to sequencing in music, especially modular synthesizers; instead of sequencing a loop of triggers for an envelope generator, the sequencer directly generates a looping envelope from its input parameters.

This enables all peaks of the envelope - which humans percieve as a rythmic event - to be locked at a rythmic intervals independently of the attack and delay times, which, in turn, enables the musician to experiment and improvise more freely with attack time and shape without loosing the rythmic structure of their composition.

With the regular approach of triggering envelopes, increasing the attack time will shift the peak of the envelope backwards, which needs to be compensated for by adjusting the micro-timing of the triggering steps, a procedure which is cumbersome at best but in general unavailable on more simple sequencers. Even when it is possible, moving the trigger point of an envelope to an earlier point in time will cause the first trigger to not fire at all on the first loop.

## How it works

TODO: Explain this properly once experiments are done

## Notes

One simple envelope looks like this:

<iframe src="https://www.desmos.com/calculator/f1qmre2ilz" width="800" height="500" style="border: 1px solid #ccc" frameborder=0></iframe>
<p hidden=true>The editable source of the Desmos snapshot above is https://www.desmos.com/calculator/hgzhy2jeis. Edit it, create a new snapshot and change the URL above so changes are tracked in git.</p>

Feel free to adjust the $a$ (attack), $d$ (decay) and $s$ (shape) values to get a feel for how this all works. You can see that the frequency of this waveform doesn't change when the inputs are adjusted. You can also see that this implementation is not procedural, but mathematical, which makes this concept powerful in multiple ways:

1. The waveform can be sampled at any frequency, it can go all the way from LFO to Audio-Range
2. You always get the same result for the same inputs, there's no dependency on previous actions

The final trick now is to generate multiple of these simple envelopes at overlapping time intervals and interpolate between them in some way to get a sequence.

## Development

This repository provides a Nix Flake and direnv-config. To start development, install any Nix-compatible package manager (I recommend [Lix](https://lix.systems/install/)) and run `nix shell` in this repo or additionally install direnv and run `direnv allow`. If you're using vscode, extension recommendations are provided.