// ModC wrap of PlayerPuppet.OnUpdate to demonstrate wrap coexistence
@wrapMethod(PlayerPuppet)
func OnUpdate(delta: Float) -> Void {
    // Pre logic C
    wrappedMethod(delta);
    // Post logic C
}
